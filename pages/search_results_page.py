"""eBay search results page: price filtering, extraction, and pagination."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import allure
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from pages.base_page import BasePage, EL
from utils.logger import get_logger
from utils.retry_handler import with_retry

if TYPE_CHECKING:
    from playwright.sync_api import Locator

logger = get_logger(__name__)


class SearchResultsPage(BasePage):
    RESULT_ITEMS = EL("Search Result Items", [
        ("css", "ul.srp-results > li.s-card"),
        ("xpath", "//ul[contains(@class,'srp-results')]/li[contains(@class,'s-card')]"),
    ])
    PRICE_MIN_INPUT = EL("Price Min Input", [
        ("css", "input.textbox__control[aria-label*='Minimum Value']"),
        ("xpath", "//input[contains(@aria-label,'Minimum Value')]"),
    ])
    PRICE_MAX_INPUT = EL("Price Max Input", [
        ("css", "input.textbox__control[aria-label*='Maximum Value']"),
        ("xpath", "//input[contains(@aria-label,'Maximum Value')]"),
    ])
    PRICE_SUBMIT_BUTTON = EL("Price Submit Button", [
        ("css", "button[aria-label='Submit price range']"),
        ("xpath", "//button[@aria-label='Submit price range']"),
    ])
    PAGINATION_NEXT = EL("Pagination Next", [
        ("css", "nav.pagination a[type='next'].pagination__next[href]"),
        ("xpath", "//nav[contains(@class,'pagination')]//a[@type='next' and contains(@class,'pagination__next') and @href]"),
        ("css", "nav.pagination a[aria-label='Go to next page'][href]"),
        ("xpath", "//nav[contains(@class,'pagination')]//a[contains(@aria-label,'next page') and @href]"),
    ])
    PAGINATION_PAGE_LINKS = EL("Pagination Page Links", [
        ("css", "nav.pagination ol.pagination__items a[type='page'][href]"),
        ("xpath", "//nav[contains(@class,'pagination')]//ol[contains(@class,'pagination__items')]//a[@type='page' and @href]"),
    ])
    NO_RESULTS_MESSAGE = EL("No Results Message", [
        ("css", ".srp-save-null-search__heading"),
        ("xpath", "//div[contains(@class,'srp-save-null-search')]//h3"),
    ])

    def wait_for_results(self, timeout_ms: int = 10000) -> None:
        try:
            self._page.wait_for_load_state("domcontentloaded", timeout=5000)
        except PlaywrightTimeout:
            logger.info("Search page did not report domcontentloaded in time")

        try:
            self.wait_for_visible(self.RESULT_ITEMS, timeout_ms=timeout_ms)
        except Exception:
            if self.is_visible(self.NO_RESULTS_MESSAGE, timeout_ms=3000):
                return
            logger.warning("Search results did not render expected result cards")

    def apply_price_filter(self, max_price: float, min_price: float | None = None) -> None:
        with allure.step(f"Apply price filter (min={min_price}, max={max_price})"):
            target_value = str(int(max_price))
            max_input = self._find_optional(self.PRICE_MAX_INPUT, timeout_ms=3000)
            if max_input is None:
                logger.warning("Price filter UI not found - applying max price via URL")
                self._ensure_price_limit_in_url(max_price)
                self.wait_for_results(timeout_ms=5000)
                return

            if min_price is not None:
                min_input = self._find_optional(self.PRICE_MIN_INPUT, timeout_ms=2000)
                if min_input is not None:
                    min_input.scroll_into_view_if_needed()
                    min_input.fill("")
                    min_input.fill(str(int(min_price)))
                    logger.info("Set min price filter to %s", int(min_price))

            max_input.scroll_into_view_if_needed()
            max_input.fill("")
            max_input.fill(target_value)
            try:
                max_input.dispatch_event("input")
                max_input.dispatch_event("change")
                max_input.press("Tab")
            except Exception:
                logger.info("Price max input did not accept extra input/change events")

            current_value = max_input.input_value().strip()
            if current_value != target_value:
                logger.warning(
                    "Price max input retained '%s' instead of '%s'",
                    current_value,
                    target_value,
                )

            submit_button = self._find_optional(self.PRICE_SUBMIT_BUTTON, timeout_ms=2000)
            if submit_button is None:
                logger.warning("Price submit button not found - applying max price via URL")
                self._ensure_price_limit_in_url(max_price)
                self.wait_for_results(timeout_ms=5000)
                return

            submit_button.scroll_into_view_if_needed()
            if not self._wait_for_enabled(submit_button, timeout_ms=3000):
                logger.warning("Price submit button stayed disabled - applying max price via URL")
                self._ensure_price_limit_in_url(max_price)
                self.wait_for_results(timeout_ms=5000)
                return

            try:
                with_retry(lambda: submit_button.click(timeout=3000))
            except Exception as exc:
                logger.warning("Price submit button click failed - applying via URL: %s", exc)
                self._ensure_price_limit_in_url(max_price)
                self.wait_for_results(timeout_ms=5000)
                return

            self._ensure_price_limit_in_url(max_price)

            self.wait_for_results(timeout_ms=5000)
            logger.info("Active search max price confirmed in URL: %s", self.current_url)

    def get_item_cards(self) -> list[Locator]:
        try:
            return self._find_all(self.RESULT_ITEMS).all()
        except Exception:
            return []

    def get_item_price(self, card: Locator) -> float | None:
        try:
            price_text = (
                card.locator("xpath=.//*[contains(@class,'s-card__price')]")
                .first
                .text_content(timeout=3000)
                or ""
            )
            return self.parse_displayed_amount(price_text)
        except Exception:
            return None

    def get_item_url(self, card: Locator) -> str | None:
        try:
            link = card.locator(
                "xpath=.//a[contains(@class,'s-card__link') and contains(@href,'/itm/')]"
            ).first
            return link.get_attribute("href", timeout=3000)
        except Exception:
            return None

    def has_next_page(self) -> bool:
        return self._get_next_page_link(timeout_ms=3000) is not None

    @allure.step("Navigate to next results page")
    def go_to_next_page(self) -> None:
        next_link = self._get_next_page_link(timeout_ms=3000)
        if next_link is None:
            raise AssertionError("Pagination requested but no enabled next-page control was found")

        previous_url = self.current_url
        with_retry(lambda: next_link.click(timeout=3000))
        try:
            self.page.wait_for_url(lambda url: url != previous_url, timeout=5000)
        except PlaywrightTimeout:
            logger.warning("Pagination click did not change the results URL")
        self.wait_for_results()

    def has_results(self) -> bool:
        return not self.is_visible(self.NO_RESULTS_MESSAGE, timeout_ms=3000)

    def collect_items_under_price(self, max_price: float, limit: int) -> list[str]:
        """Collect up to `limit` result URLs where each visible card price is <= `max_price`."""
        urls: list[str] = []
        for card in self.get_item_cards():
            if len(urls) >= limit:
                break

            price = self.get_item_price(card)
            if price is None or price > max_price:
                continue

            url = self.get_item_url(card)
            if url:
                urls.append(url)

        return urls

    def _wait_for_enabled(self, locator, timeout_ms: int) -> bool:
        deadline = time.time() + (timeout_ms / 1000.0)
        while time.time() < deadline:
            try:
                if not locator.is_disabled():
                    return True
            except Exception:
                return False
            self.page.wait_for_timeout(100)
        return False

    def _wait_for_price_limit_in_url(self, max_price: float, timeout_ms: int) -> bool:
        target = f"_udhi={int(max_price)}"
        try:
            self.page.wait_for_url(lambda url: target in url, timeout=timeout_ms)
            return True
        except PlaywrightTimeout:
            return target in self.current_url

    def _ensure_price_limit_in_url(self, max_price: float) -> None:
        if self._wait_for_price_limit_in_url(max_price, timeout_ms=1500):
            return

        self._navigate_with_max_price(max_price)
        if not self._wait_for_price_limit_in_url(max_price, timeout_ms=5000):
            raise AssertionError(f"Search max price _udhi={int(max_price)} was not applied to the URL")

    def _navigate_with_max_price(self, max_price: float) -> None:
        parsed = urlparse(self.current_url)
        query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query_params["_udhi"] = str(int(max_price))

        filtered_url = urlunparse(
            parsed._replace(query=urlencode(query_params, doseq=True))
        )
        logger.info("Applying max price via URL: %s", filtered_url)
        self.page.goto(filtered_url, wait_until="domcontentloaded")

    def _get_next_page_link(self, timeout_ms: int) -> Locator | None:
        next_link = self._find_optional(self.PAGINATION_NEXT, timeout_ms=timeout_ms)
        if self._is_enabled_pagination_link(next_link):
            return next_link

        page_links = self._find_all_optional(self.PAGINATION_PAGE_LINKS, timeout_ms=timeout_ms)
        if page_links is None:
            return None

        links = page_links.all()
        current_page_index = -1
        for index, link in enumerate(links):
            if (link.get_attribute("aria-current") or "").strip().lower() == "page":
                current_page_index = index
                break

        if current_page_index == -1:
            return None

        for link in links[current_page_index + 1:]:
            if self._is_enabled_pagination_link(link):
                return link

        return None

    def _is_enabled_pagination_link(self, link: Locator | None) -> bool:
        if link is None:
            return False

        try:
            if link.is_disabled():
                return False
        except Exception:
            pass

        aria_disabled = (link.get_attribute("aria-disabled") or "").strip().lower()
        href = (link.get_attribute("href") or "").strip()
        return aria_disabled != "true" and bool(href)
