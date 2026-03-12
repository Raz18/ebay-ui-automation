"""Base page object that all page classes inherit from.

Wraps LocatorEngine for element resolution and RetryHandler for
transient failure recovery. Tests never instantiate this directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import allure
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from config.settings import Settings
from utils.locator_engine import ElementLocators, LocatorEngine  # noqa: F401
from utils.logger import get_logger
from utils.price_parser import ParsedPrice, parse_price_info
from utils.retry_handler import with_retry
from utils.screenshot_helper import capture_screenshot

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page

logger = get_logger(__name__)

# Re-export so page objects only need: from pages.base_page import BasePage, EL
EL = ElementLocators


class BasePage:
    """Base class for all eBay page objects."""

    def __init__(self, page: Page, settings: Settings | None = None) -> None:
        self._page = page
        self._settings = settings or Settings.from_env()
        self._engine = LocatorEngine(page, self._settings)

    def _find(self, element: ElementLocators, timeout_ms: int | None = None) -> Locator:
        return self._engine.find(element, timeout_ms=timeout_ms)

    def _find_all(self, element: ElementLocators, timeout_ms: int | None = None) -> Locator:
        return self._engine.find_all(element, timeout_ms=timeout_ms)

    def _find_optional(
        self, element: ElementLocators, timeout_ms: int | None = None,
    ) -> Locator | None:
        return self._engine.find_optional(element, timeout_ms=timeout_ms)

    def _find_all_optional(
        self, element: ElementLocators, timeout_ms: int | None = None,
    ) -> Locator | None:
        return self._engine.find_all_optional(element, timeout_ms=timeout_ms)

    def _peek_optional(
        self,
        element: ElementLocators,
        timeout_ms: int = 500,
    ) -> Locator | None:
        return self._engine.peek_optional(element, timeout_ms=timeout_ms)

    def _peek_all_optional(
        self,
        element: ElementLocators,
        timeout_ms: int = 500,
    ) -> Locator | None:
        return self._engine.peek_all_optional(element, timeout_ms=timeout_ms)

    # --- Actions ---

    def click(self, element: ElementLocators, timeout_ms: int | None = None) -> None:
        with allure.step(f"Click '{element.name}'"):
            with_retry(lambda: self._find(element, timeout_ms).click())
            logger.info("Clicked '%s'", element.name)

    def fill(self, element: ElementLocators, text: str, timeout_ms: int | None = None) -> None:
        with allure.step(f"Fill '{element.name}'"):
            with_retry(lambda: self._find(element, timeout_ms).fill(text))
            logger.info("Filled '%s' with '%s'", element.name, text)

    def get_text(self, element: ElementLocators, timeout_ms: int | None = None) -> str:
        with allure.step(f"Get text from '{element.name}'"):
            text = with_retry(lambda: self._find(element, timeout_ms).text_content()) or ""
            return text.strip()

    def parse_displayed_price(self, text: str) -> ParsedPrice:
        required_currency = (
            self._settings.PREFERRED_CURRENCY
            if self._settings.STRICT_CURRENCY_VALIDATION
            else None
        )
        return parse_price_info(
            text,
            preferred_currency=self._settings.PREFERRED_CURRENCY,
            required_currency=required_currency,
        )

    def parse_displayed_amount(self, text: str) -> float:
        return self.parse_displayed_price(text).amount

    def wait_for_visible(self, element: ElementLocators, timeout_ms: int | None = None) -> None:
        self._find(element, timeout_ms)

    # --- State queries ---

    def is_visible(self, element: ElementLocators, timeout_ms: int | None = None) -> bool:
        return self._find_optional(element, timeout_ms or 3000) is not None

    def element_count(self, element: ElementLocators, timeout_ms: int | None = None) -> int:
        locator = self._find_all_optional(element, timeout_ms or 3000)
        return locator.count() if locator is not None else 0

    # --- Navigation ---

    def navigate(self, url: str) -> None:
        with allure.step(f"Navigate to '{url}'"):
            self._page.goto(url, wait_until="domcontentloaded")
            logger.info("Navigated to %s", url)

    def wait_for_page_load(self) -> None:
        try:
            self._page.wait_for_load_state("load", timeout=10000)
        except PlaywrightTimeout:
            logger.info("Page did not reach load state within timeout")

    @property
    def page(self) -> Page:
        return self._page

    @property
    def current_url(self) -> str:
        return self._page.url

    def is_blocked_by_captcha(self) -> bool:
        """Check whether the current page is a CAPTCHA / bot-verification screen."""
        url = self.current_url.lower()
        if "captcha" in url or "splashui" in url:
            return True
        try:
            title = self._page.title().lower()
        except Exception:
            return False
        return "captcha" in title or "verify yourself" in title

    def take_screenshot(self, name: str) -> None:
        capture_screenshot(self._page, name)
