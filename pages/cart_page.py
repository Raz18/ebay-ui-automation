"""eBay shopping cart page: subtotal parsing, item count, itemized prices."""

from __future__ import annotations

import time

import allure
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from pages.base_page import BasePage, EL
from utils.logger import get_logger
from utils.price_parser import ParsedPrice

logger = get_logger(__name__)


class CartPage(BasePage):
    # --- Locators ---

    BLOCKING_ATC_DIALOG = EL("Blocking Add-to-Cart Dialog", [
        ("css", "div[data-testid='ux-overlay'][aria-hidden='false'], div.lightbox-dialog__window.keyboard-trap--active"),
        ("xpath", "//div[@data-testid='ux-overlay' and @aria-hidden='false'] | //div[contains(@class,'lightbox-dialog__window') and contains(@class,'keyboard-trap--active')]"),
    ])
    BLOCKING_ATC_DIALOG_CLOSE = EL("Blocking Add-to-Cart Dialog Close", [
        ("css", "div[data-testid='ux-overlay'][aria-hidden='false'] button.lightbox-dialog__close, div.lightbox-dialog__window.keyboard-trap--active button.lightbox-dialog__close"),
        ("css", "div[data-testid='ux-overlay'][aria-hidden='false'] button[aria-label='Close dialog'], div.lightbox-dialog__window.keyboard-trap--active button[aria-label='Close dialog']"),
        ("xpath", "//div[@data-testid='ux-overlay' and @aria-hidden='false']//button[contains(@class,'lightbox-dialog__close')] | //div[contains(@class,'lightbox-dialog__window') and contains(@class,'keyboard-trap--active')]//button[contains(@class,'lightbox-dialog__close')]"),
    ])
    HEADER_CART_BADGE = EL("Header Cart Badge", [
        ("css", "div.gh-cart a.gh-flyout__target[href*='cart.ebay.com']"),
        ("xpath", "//div[contains(@class,'gh-cart')]//a[contains(@href,'cart.ebay.com')]"),
    ])
    HEADER_CART_EXPAND = EL("Header Cart Expand Button", [
        ("css", "div.gh-cart button.gh-flyout__target-a11y-btn"),
        ("xpath", "//div[contains(@class,'gh-cart')]//button[contains(@class,'gh-flyout__target-a11y-btn')]"),
    ])
    MINI_CART_VIEW_CART = EL("Mini Cart View Cart", [
        ("css", "div.gh-minicart-actions a.gh-minicart-actions-btn--secondary[href*='cart.ebay.com']"),
        ("xpath", "//div[contains(@class,'gh-minicart-actions')]//a[contains(@href,'cart.ebay.com') and normalize-space()='View cart']"),
    ])

    CART_ITEMS = EL("Cart Items List", [
        ("css", "div.cart-bucket .cart-bucket-lineitem"),
        ("xpath", "//div[contains(@class,'cart-bucket-lineitem')]"),
    ])
    ITEM_TITLE = EL("Cart Item Title", [
        ("css", ".cart-bucket-lineitem .item-title a"),
        ("xpath", "//div[contains(@class,'cart-bucket-lineitem')]//a[contains(@class,'item-title')]"),
    ])
    ITEM_PRICE = EL("Cart Item Price", [
        ("css", ".cart-bucket-lineitem .item-price"),
        ("xpath", "//div[contains(@class,'cart-bucket-lineitem')]//*[contains(@class,'item-price')]"),
    ])
    ITEM_QUANTITY = EL("Cart Item Quantity", [
        ("test_id", "qty-input"),
        ("css", "input.qty-input"),
    ])
    SUBTOTAL = EL("Cart Subtotal", [
        ("test_id", "SUBTOTAL"),
        ("css", "[data-test-id='SUBTOTAL']"),
        ("xpath", "//*[@data-test-id='SUBTOTAL']"),
    ])
    ITEM_TOTAL = EL("Cart Item Total", [
        ("test_id", "ITEM_TOTAL"),
        ("css", "[data-test-id='ITEM_TOTAL']"),
    ])
    ESTIMATED_TOTAL = EL("Cart Estimated Total", [
        ("test_id", "ESTIMATED_TOTAL"),
        ("css", "[data-test-id='ESTIMATED_TOTAL']"),
    ])
    SUMMARY_SUBTOTAL_ROW = EL("Cart Summary Subtotal Row", [
        ("xpath", "//*[normalize-space()='Subtotal']/ancestor::*[contains(@class,'cart-summary-line-item')][1]"),
        ("xpath", "//div[contains(@class,'cart-summary-line-item')][.//div[contains(@class,'total-row')]]"),
    ])
    ORDER_SUMMARY_PANEL = EL("Cart Order Summary Panel", [
        ("css", "[data-test-id='cart-summary']"),
        ("xpath", "//div[contains(@class,'cartsummary')]"),
    ])
    ITEM_COUNT = EL("Cart Item Count", [
        ("css", ".cart-count"),
        ("xpath", "//span[contains(@class,'cart-count')]"),
    ])
    REMOVE_BUTTON = EL("Remove Item Button", [
        ("test_id", "cart-remove-item"),
        ("text", "Remove"),
    ])
    CHECKOUT_BUTTON = EL("Checkout Button", [
        ("test_id", "cta-top"),
        ("text", "Go to checkout"),
    ])
    EMPTY_CART_MESSAGE = EL("Empty Cart Message", [
        ("css", ".empty-cart .font-title-3"),
        ("text", "You don't have any items"),
    ])

    # --- Actions ---

    @allure.step("Navigate to shopping cart")
    def navigate_to_cart(self) -> CartPage:
        if self._is_on_cart_url():
            logger.info("Already on cart page: %s", self.current_url)
            return self

        self._dismiss_blocking_add_to_cart_dialog(timeout_ms=10000)

        if not self._open_cart_flyout():
            raise RuntimeError(
                f"Could not open the mini-cart from the cart badge at {self.current_url}"
            )

        if not self._click_view_cart_from_flyout():
            raise RuntimeError(
                f"Cart badge flow opened, but 'View cart' navigation could not be completed from {self.current_url}"
            )

        self._wait_for_cart_url()
        self.wait_for_page_load()
        return self

    def _dismiss_blocking_add_to_cart_dialog(self, timeout_ms: int = 8000) -> None:
        deadline = time.time() + (timeout_ms / 1000.0)

        while time.time() < deadline:
            if self._find_optional(self.BLOCKING_ATC_DIALOG, timeout_ms=300) is None:
                return

            if self._find_optional(self.BLOCKING_ATC_DIALOG_CLOSE, timeout_ms=500) is not None:
                self.click(self.BLOCKING_ATC_DIALOG_CLOSE, timeout_ms=2000)
                if self._wait_for_blocking_dialog_to_close(timeout_ms=5000):
                    logger.info("Dismissed blocking add-to-cart dialog before cart navigation")
                    return

            try:
                self.page.keyboard.press("Escape")
                if self._wait_for_blocking_dialog_to_close(timeout_ms=1500):
                    logger.info("Dismissed blocking add-to-cart dialog with Escape")
                    return
            except Exception:
                logger.debug("Escape did not dismiss the blocking add-to-cart dialog")

            self.page.wait_for_timeout(150)

        if self._find_optional(self.BLOCKING_ATC_DIALOG, timeout_ms=500) is not None:
            raise RuntimeError(
                "Blocking add-to-cart dialog remained open, preventing cart navigation"
            )

    def _wait_for_blocking_dialog_to_close(self, timeout_ms: int = 5000) -> bool:
        deadline = time.time() + (timeout_ms / 1000.0)

        while time.time() < deadline:
            if self._find_optional(self.BLOCKING_ATC_DIALOG, timeout_ms=250) is None:
                return True
            self.page.wait_for_timeout(100)

        return False

    def _is_on_cart_url(self) -> bool:
        return "cart.ebay.com" in self.current_url.lower()

    def _open_cart_flyout(self) -> bool:
        if self._is_on_cart_url():
            return True

        if self._find_optional(self.MINI_CART_VIEW_CART, timeout_ms=1000) is not None:
            return True

        cart_badge = self._find_optional(self.HEADER_CART_BADGE, timeout_ms=5000)
        if cart_badge is None:
            return False

        try:
            cart_badge.click(timeout=5000)
            logger.info("Clicked cart badge")
        except Exception as exc:
            logger.warning("Could not click cart badge: %s", exc)
            self._dismiss_blocking_add_to_cart_dialog(timeout_ms=15000)
            cart_badge = self._find_optional(self.HEADER_CART_BADGE, timeout_ms=5000)
            if cart_badge is None:
                return False
            cart_badge.click(timeout=5000)
            logger.info("Clicked cart badge after dismissing overlay")

        if self._is_on_cart_url():
            logger.info("Cart badge click navigated directly to the cart page")
            return True

        if self._find_optional(self.MINI_CART_VIEW_CART, timeout_ms=4000) is not None:
            logger.info("Mini-cart became available after cart badge click")
            return True

        try:
            cart_badge.hover(timeout=3000)
            logger.info("Hovered cart badge after click to reveal mini-cart")
        except Exception as exc:
            logger.warning("Could not hover cart badge after click: %s", exc)

        if self._find_optional(self.MINI_CART_VIEW_CART, timeout_ms=3000) is not None:
            return True

        expand_button = self._find_optional(self.HEADER_CART_EXPAND, timeout_ms=2000)
        if expand_button is not None:
            try:
                expand_button.click(timeout=5000)
                logger.info("Opened cart flyout via expand button after cart badge click")
            except Exception as exc:
                logger.warning("Could not click cart expand button: %s", exc)

        return self._find_optional(self.MINI_CART_VIEW_CART, timeout_ms=5000) is not None

    def _click_view_cart_from_flyout(self) -> bool:
        if self._is_on_cart_url():
            return True

        view_cart = self._find_optional(self.MINI_CART_VIEW_CART, timeout_ms=5000)
        if view_cart is None:
            return False

        try:
            view_cart.click(timeout=5000)
        except Exception as exc:
            logger.warning("Could not click mini-cart 'View cart': %s", exc)
            self._dismiss_blocking_add_to_cart_dialog(timeout_ms=15000)
            view_cart = self._find_optional(self.MINI_CART_VIEW_CART, timeout_ms=5000)
            if view_cart is None:
                return False
            view_cart.click(timeout=5000)
        logger.info("Navigating to cart via mini-cart 'View cart'")
        return True

    def _wait_for_cart_url(self, timeout_ms: int = 15000) -> None:
        try:
            self.page.wait_for_url("**cart.ebay.com**", timeout=timeout_ms)
            logger.info("Reached cart URL: %s", self.current_url)
        except PlaywrightTimeout as exc:
            raise RuntimeError(
                f"Cart navigation did not reach cart.ebay.com; current URL is {self.current_url}"
            ) from exc

    def get_cart_subtotal(self) -> float:
        """Parse the displayed subtotal as a float."""
        for element, label in (
            (self.SUBTOTAL, "Cart subtotal"),
            (self.ITEM_TOTAL, "Cart item total"),
            (self.ESTIMATED_TOTAL, "Cart estimated total"),
            (self.SUMMARY_SUBTOTAL_ROW, "Cart summary subtotal row"),
            (self.ORDER_SUMMARY_PANEL, "Cart order summary panel"),
        ):
            try:
                text = self.get_text(element)
                parsed = self.parse_displayed_price(text)
                logger.info("%s: %s %.2f (raw: '%s')", label, parsed.currency, parsed.amount, text)
                return parsed.amount
            except Exception:
                logger.info("%s locator not found or not parseable", label)

        price_infos = self.get_itemized_price_infos()
        if price_infos:
            currencies = {price.currency for price in price_infos}
            if len(currencies) == 1 and self._settings.PREFERRED_CURRENCY in currencies:
                total = sum(price.amount for price in price_infos)
                logger.info(
                    "Computed subtotal from itemized prices: %s %.2f",
                    self._settings.PREFERRED_CURRENCY,
                    total,
                )
                return total

            raise ValueError(
                "Could not determine cart subtotal from summary locators, and itemized prices "
                f"use incompatible currencies: {sorted(currencies)}"
            )

        raise ValueError(
            "Could not determine cart subtotal from subtotal, estimated total, summary row, or order summary"
        )

    def get_item_count(self) -> int:
        try:
            text = self.get_text(self.ITEM_COUNT)
            digits = "".join(char for char in text if char.isdigit())
            if digits:
                return int(digits)
        except Exception:
            logger.info("Cart item count badge not found - falling back to cart rows")

        return self.element_count(self.CART_ITEMS, timeout_ms=3000)

    def get_itemized_price_infos(self) -> list[ParsedPrice]:
        price_infos: list[ParsedPrice] = []
        try:
            price_locators = self._find_all(self.ITEM_PRICE)
            for price_element in price_locators.all():
                text = price_element.text_content() or ""
                price_infos.append(self.parse_displayed_price(text))
        except Exception:
            logger.warning("Could not extract itemized prices")
        return price_infos

    def is_cart_empty(self) -> bool:
        return self.is_visible(self.EMPTY_CART_MESSAGE, timeout_ms=3000)
