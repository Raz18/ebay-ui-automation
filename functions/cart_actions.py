"""Cart orchestration: add items and assert totals within budget."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import allure
import pytest

from config.settings import Settings
from pages.cart_page import CartPage
from pages.product_page import ProductPage
from pages.search_results_page import SearchResultsPage
from utils.logger import get_logger
from utils.screenshot_helper import capture_screenshot

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = get_logger(__name__)


@dataclass(frozen=True)
class AddedCartItem:
    url: str
    title: str
    price: float


def add_items_to_cart(page: Page, urls: list[str]) -> list[AddedCartItem]:
    """Open each product in a separate tab, add it to cart, then return to the search tab."""
    added_items: list[AddedCartItem] = []
    search_results_url = page.url

    settings = Settings.from_env()
    for index, url in enumerate(urls, start=1):
        if index > 1 and settings.ANTI_BOT_DELAY_MAX > 0:
            delay = random.uniform(settings.ANTI_BOT_DELAY_MIN, settings.ANTI_BOT_DELAY_MAX)
            logger.info("Waiting %.1fs before next item to reduce bot detection", delay)
            time.sleep(delay)

        logger.info("Adding item %d/%d: %s", index, len(urls), url)
        product_page = _open_product_tab(page)
        product = ProductPage(product_page)
        try:
            added_item = _add_single_item(
                product,
                url,
                close_modal_after_add=False,
            )
            if added_item is None:
                continue

            added_items.append(added_item)
            capture_screenshot(product_page, f"added_{index}_{_safe_name(added_item.title)}")
        except Exception as exc:
            logger.error("Failed to add item %d/%d: %s", index, len(urls), exc)
            capture_screenshot(product_page, f"add_item_failed_{index}")
        finally:
            _close_product_tab(product_page)
            _restore_search_results_tab(page, search_results_url)

    return added_items


def _add_single_item(
    product: ProductPage,
    url: str,
    close_modal_after_add: bool = False,
) -> AddedCartItem | None:
    product.navigate(url)
    product.wait_until_ready()

    if product.is_blocked_by_captcha():
        logger.warning("CAPTCHA detected on product page — skipping: %s", url)
        return None

    if not product.has_add_to_cart():
        logger.warning("No Add to Cart button found - skipping: %s", url)
        return None

    product.select_first_variants()
    title = _read_title(product)
    price = product.get_product_price()
    previous_cart_count = product.get_header_cart_count()
    product.click_add_to_cart()

    if product.is_blocked_by_captcha():
        logger.warning("CAPTCHA detected after clicking Add to Cart — skipping: %s", url)
        return None

    product.wait_for_add_to_cart_confirmation(previous_count=previous_cart_count)
    product.handle_post_cart_modal(
        prefer_close_button=close_modal_after_add,
        appear_timeout_ms=20000 if close_modal_after_add else 3000,
    )
    return AddedCartItem(url=url, title=title, price=price)


def _read_title(product: ProductPage) -> str:
    try:
        return product.get_product_title()
    except Exception:
        return "product"


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_")[:50] or "product"


def _open_product_tab(search_page: Page) -> Page:
    """Open a temporary product tab in the same browser context."""
    product_page = search_page.context.new_page()
    try:
        product_page.bring_to_front()
    except Exception:
        pass
    return product_page


def _close_product_tab(product_page: Page) -> None:
    """Close the temporary product tab once the add-to-cart attempt is finished."""
    try:
        if not product_page.is_closed():
            product_page.close(run_before_unload=False)
    except Exception:
        pass


def _restore_search_results_tab(search_page: Page, search_results_url: str) -> None:
    """Return focus to the original search results tab without reloading unless needed."""
    if not search_results_url:
        return

    try:
        search_page.bring_to_front()
    except Exception:
        pass

    if search_page.url == search_results_url:
        return

    logger.info("Restoring search results page: %s", search_results_url)
    search_page.goto(search_results_url, wait_until="domcontentloaded")
    SearchResultsPage(search_page).wait_for_results(timeout_ms=5000)


@allure.step("Assert cart total does not exceed the budget")
def assert_cart_total_not_exceeds(
    page: Page,
    budget_per_item: float,
    items_count: int,
) -> None:
    """Open the cart and verify subtotal/total <= budget_per_item * items_count."""
    cart = CartPage(page)
    cart.navigate_to_cart()

    if cart.is_blocked_by_captcha():
        capture_screenshot(page, "cart_blocked")
        pytest.skip("Cart page was blocked by CAPTCHA — manual intervention required")

    try:
        actual_total = cart.get_cart_subtotal()
    except Exception as exc:
        capture_screenshot(page, "cart_total_unreadable")
        if cart.is_blocked_by_captcha():
            capture_screenshot(page, "cart_blocked_during_read")
            pytest.skip("Cart page was blocked by CAPTCHA while reading total — manual intervention required")
        raise AssertionError(f"Could not read cart total reliably from the cart page: {exc}") from exc

    threshold = budget_per_item * items_count

    capture_screenshot(page, "cart_assertion")

    assert actual_total <= threshold, (
        f"Cart total {actual_total:.2f} exceeds budget "
        f"{budget_per_item:.2f} x {items_count} = {threshold:.2f}"
    )
