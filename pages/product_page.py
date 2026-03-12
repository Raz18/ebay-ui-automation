"""eBay product detail page: variant selection, add to cart, post-cart modal."""

from __future__ import annotations

import time

import random

import allure

from pages.base_page import BasePage, EL
from utils.logger import get_logger

logger = get_logger(__name__)


class ProductPage(BasePage):
    VARIANT_PEEK_TIMEOUT_MS = 500

    # --- Locators ---

    ADD_TO_CART = EL("Add to Cart Button", [
        ("test_id", "x-atc-action"),
        ("text", "Add to cart"),
    ])
    BUY_IT_NOW = EL("Buy It Now Button", [
        ("test_id", "x-bin-action"),
        ("text", "Buy It Now"),
    ])
    PRODUCT_TITLE = EL("Product Title", [
        ("css", "h1.x-item-title__mainTitle span"),
        ("xpath", "//h1[contains(@class,'x-item-title__mainTitle')]//span"),
    ])
    PRODUCT_PRICE = EL("Product Price", [
        ("css", "div.x-price-primary"),
        ("xpath", "//div[contains(@class,'x-price-primary')]"),
    ])

    # Variant selectors
    SIZE_DROPDOWN = EL("Size Dropdown", [
        ("label", "Size"),
        ("css", "select[aria-label*='Size']"),
    ])
    COLOR_DROPDOWN = EL("Color Dropdown", [
        ("label", "Color"),
        ("css", "select[aria-label*='Color']"),
    ])
    VARIANT_SELECT = EL("Variant Select", [
        ("css", "select.x-msku__select-box-1000"),
        ("xpath", "//div[contains(@class,'vim x-msku')]//select"),
    ])
    CUSTOM_VARIANT_LISTBOX = EL("Custom Variant Listbox", [
        (
            "css",
            "div.vim.x-sku button.listbox-button__control[aria-haspopup='listbox'], "
            "div.vim.x-msku button.listbox-button__control[aria-haspopup='listbox']",
        ),
        (
            "xpath",
            "//div[contains(@class,'vim') and (contains(@class,'x-sku') or contains(@class,'x-msku'))]"
            "//button[@aria-haspopup='listbox' and contains(@class,'listbox-button__control')]",
        ),
    ])
    SIZE_BUTTON_GROUP = EL("Size Button Group", [
        ("test_id", "x-msku__select-box"),
        ("css", "div[data-testid='x-msku__select-box'] button"),
    ])
    COLOR_BUTTON_GROUP = EL("Color Button/Swatch", [
        ("css", "ul.x-msku__box-cont li button"),
        ("xpath", "//ul[contains(@class,'x-msku__box-cont')]//button"),
    ])
    QUANTITY_INPUT = EL("Quantity Input", [
        ("css", "input[name='quantity']"),
        ("css", "input#qtyTextBox"),
    ])

    # Cart confirmation
    CART_LAYER = EL("Post Add-to-Cart Layer", [
        ("css", "div[data-testid='ux-overlay'][aria-hidden='false'], div.lightbox-dialog__window.keyboard-trap--active"),
        ("xpath", "//div[@data-testid='ux-overlay' and @aria-hidden='false'] | //div[contains(@class,'lightbox-dialog__window') and contains(@class,'keyboard-trap--active')]"),
    ])
    GO_TO_CART = EL("Go to Cart Button", [
        ("text", "Go to cart"),
        ("css", "a[href*='cart.ebay.com']"),
    ])
    SEE_IN_CART = EL("See in Cart Button", [
        ("text", "See in cart"),
        ("css", "a.ux-call-to-action[href*='cart.ebay.com']"),
    ])
    KEEP_SHOPPING = EL("Keep Shopping Button", [
        ("text", "Keep shopping"),
        ("test_id", "ux-overlay-close"),
    ])
    CLOSE_CART_LAYER = EL("Close Add-to-Cart Dialog", [
        ("css", "div[data-testid='ux-overlay'][aria-hidden='false'] button.lightbox-dialog__close, div.lightbox-dialog__window.keyboard-trap--active button.lightbox-dialog__close"),
        ("xpath", "//div[@data-testid='ux-overlay' and @aria-hidden='false']//button[contains(@class,'lightbox-dialog__close')] | //div[contains(@class,'lightbox-dialog__window') and contains(@class,'keyboard-trap--active')]//button[contains(@class,'lightbox-dialog__close')]"),
    ])
    HEADER_CART_COUNT = EL("Header Cart Count", [
        ("css", "#gh-cart-n"),
        ("xpath", "//span[@id='gh-cart-n']"),
    ])

    # --- Product info ---

    def wait_until_ready(self, timeout_ms: int = 10000) -> None:
        """Wait for a practical product-page ready signal instead of network idle."""
        if self._find_optional(self.ADD_TO_CART, timeout_ms=timeout_ms) is not None:
            return
        if self._find_optional(self.BUY_IT_NOW, timeout_ms=3000) is not None:
            return
        if self._find_optional(self.PRODUCT_TITLE, timeout_ms=3000) is not None:
            return
        logger.warning("Product page did not expose a ready signal within %sms", timeout_ms)

    def get_product_title(self) -> str:
        return self.get_text(self.PRODUCT_TITLE)

    def get_product_price(self) -> float:
        return self.parse_displayed_price(self.get_text(self.PRODUCT_PRICE)).amount

    # --- Variant selection ---

    def has_add_to_cart(self) -> bool:
        return self.is_visible(self.ADD_TO_CART, timeout_ms=5000)

    @allure.step("Select random available variant")
    def select_first_variants(self) -> None:
        """Pick a random available value in every variant control on the page."""
        if self._peek_optional(self.SIZE_DROPDOWN, timeout_ms=self.VARIANT_PEEK_TIMEOUT_MS) is not None:
            self._try_select_dropdown_variant(self.SIZE_DROPDOWN, "Size")
        if self._peek_optional(self.COLOR_DROPDOWN, timeout_ms=self.VARIANT_PEEK_TIMEOUT_MS) is not None:
            self._try_select_dropdown_variant(self.COLOR_DROPDOWN, "Color")
        if self._peek_optional(self.VARIANT_SELECT, timeout_ms=self.VARIANT_PEEK_TIMEOUT_MS) is not None:
            self._try_select_dropdown_variant(self.VARIANT_SELECT, "Variant")
        if self._peek_all_optional(self.CUSTOM_VARIANT_LISTBOX, timeout_ms=self.VARIANT_PEEK_TIMEOUT_MS) is not None:
            self._try_select_custom_listbox_variants()
        if self._peek_all_optional(self.SIZE_BUTTON_GROUP, timeout_ms=self.VARIANT_PEEK_TIMEOUT_MS) is not None:
            self._try_select_button_variant(self.SIZE_BUTTON_GROUP, "Size buttons")
        if self._peek_all_optional(self.COLOR_BUTTON_GROUP, timeout_ms=self.VARIANT_PEEK_TIMEOUT_MS) is not None:
            self._try_select_button_variant(self.COLOR_BUTTON_GROUP, "Color buttons")
        self._try_set_random_quantity()

    def _try_select_dropdown_variant(self, element: EL, name: str) -> None:
        locator = self._find_optional(element, timeout_ms=2000)
        if locator is None:
            return

        try:
            options = locator.locator("option").all()
            valid = [
                option for option in options
                if self._is_valid_select_option(option.get_attribute("value"), option.text_content())
                and option.get_attribute("disabled") is None
            ]
            if not valid:
                return

            choice = random.choice(valid)
            value = choice.get_attribute("value") or ""
            locator.select_option(value=value)
            logger.info("Selected random %s option: %s", name, (choice.text_content() or "").strip())
        except Exception as exc:
            logger.warning("Could not select %s dropdown: %s", name, exc)

    def _try_set_random_quantity(self, max_qty: int = 3) -> None:
        qty_input = self._peek_optional(self.QUANTITY_INPUT, timeout_ms=self.VARIANT_PEEK_TIMEOUT_MS)
        if qty_input is None:
            return

        try:
            qty = random.randint(1, max_qty)
            qty_input.fill(str(qty))
            logger.info("Set quantity to %d", qty)
        except Exception as exc:
            logger.warning("Could not set quantity: %s", exc)

    def _try_select_button_variant(self, element: EL, name: str) -> None:
        buttons = self._find_all_optional(element, timeout_ms=2000)
        if buttons is None:
            return

        try:
            available = [
                button for button in buttons.all()
                if button.get_attribute("disabled") is None
                and "unselectable" not in (button.get_attribute("class") or "")
            ]
            if not available:
                return

            random.choice(available).click()
            logger.info("Clicked random %s option", name)
        except Exception as exc:
            logger.warning("Could not click %s button option: %s", name, exc)

    def _try_select_custom_listbox_variants(self) -> None:
        controls = self._find_all_optional(self.CUSTOM_VARIANT_LISTBOX, timeout_ms=2000)
        if controls is None:
            return

        for control in controls.all():
            try:
                if control.get_attribute("disabled") is not None:
                    continue
                if not control.is_visible():
                    continue

                control.click()
                options = control.locator(
                    "xpath=ancestor::*[contains(@class,'listbox-button')][1]//*[@role='listbox']//*[@role='option']"
                ).all()
                valid = [option for option in options if self._is_valid_listbox_option(option)]
                if not valid:
                    self.page.keyboard.press("Escape")
                    continue

                choice = random.choice(valid)
                option_text = (choice.text_content() or "").strip()
                choice.click()
                logger.info("Selected random custom listbox option: %s", option_text)
            except Exception as exc:
                logger.warning("Could not select custom variant listbox option: %s", exc)
                try:
                    self.page.keyboard.press("Escape")
                except Exception:
                    pass

    @staticmethod
    def _is_valid_select_option(value: str | None, text: str | None) -> bool:
        normalized_value = (value or "").strip()
        normalized_text = (text or "").strip().lower()
        return normalized_value not in ("", "-1") and normalized_text not in ("", "select")

    @staticmethod
    def _is_valid_listbox_option(option) -> bool:
        option_text = (option.text_content() or "").strip().lower()
        sku_value = option.get_attribute("data-sku-value-name")
        if option.get_attribute("aria-disabled") == "true":
            return False
        if sku_value:
            return True
        return option_text not in ("", "select", "selectselected")

    # --- Cart actions ---

    def get_header_cart_count(self) -> int | None:
        locator = self._find_optional(self.HEADER_CART_COUNT, timeout_ms=1500)
        if locator is None:
            return None

        text = (locator.text_content() or "").strip()
        digits = "".join(char for char in text if char.isdigit())
        return int(digits) if digits else None

    @allure.step("Click Add to Cart")
    def click_add_to_cart(self) -> None:
        self.click(self.ADD_TO_CART)

    def wait_for_add_to_cart_confirmation(
        self,
        previous_count: int | None = None,
        timeout_ms: int = 7000,
    ) -> None:
        """Wait for one of the expected post-add signals without a fixed sleep."""
        deadline = time.time() + (timeout_ms / 1000.0)

        while time.time() < deadline:
            if self.is_visible(self.CART_LAYER, timeout_ms=250):
                logger.info("Detected add-to-cart overlay")
                return

            if "cart" in self.current_url:
                logger.info("Detected cart navigation after add-to-cart")
                return

            current_count = self.get_header_cart_count()
            if (
                previous_count is not None
                and current_count is not None
                and current_count > previous_count
            ):
                logger.info(
                    "Header cart count increased from %s to %s",
                    previous_count,
                    current_count,
                )
                return

            self.page.wait_for_timeout(200)

        logger.info("No explicit add-to-cart confirmation signal detected")

    @allure.step("Handle post-add-to-cart modal")
    def handle_post_cart_modal(
        self,
        prefer_close_button: bool = False,
        appear_timeout_ms: int | None = None,
    ) -> None:
        """Dismiss the 'Added to cart' confirmation overlay when present."""
        wait_timeout_ms = appear_timeout_ms if appear_timeout_ms is not None else (
            15000 if prefer_close_button else 3000
        )

        if not self._wait_for_cart_layer_to_appear(timeout_ms=wait_timeout_ms):
            return

        if prefer_close_button and self._close_post_cart_modal_via_x():
            return

        if self.is_visible(self.KEEP_SHOPPING, timeout_ms=1500):
            self.click(self.KEEP_SHOPPING)
            self._wait_for_cart_layer_to_close()
            logger.info("Closed post-add overlay via Keep shopping")
            return

        if self._close_post_cart_modal_via_x():
            return

        try:
            self.page.keyboard.press("Escape")
            self._wait_for_cart_layer_to_close()
            logger.info("Attempted to close post-add overlay with Escape")
        except Exception as exc:
            logger.warning("Could not dismiss post-add overlay: %s", exc)

    def _wait_for_cart_layer_to_appear(self, timeout_ms: int = 3000) -> bool:
        deadline = time.time() + (timeout_ms / 1000.0)

        while time.time() < deadline:
            if self.is_visible(self.CART_LAYER, timeout_ms=300):
                return True
            if self.is_visible(self.CLOSE_CART_LAYER, timeout_ms=300):
                return True
            self.page.wait_for_timeout(100)

        logger.info("Post-add-to-cart overlay did not appear within %sms", timeout_ms)
        return False

    def _close_post_cart_modal_via_x(self, timeout_ms: int = 3000) -> bool:
        if not self.is_visible(self.CLOSE_CART_LAYER, timeout_ms=timeout_ms):
            return False

        self.click(self.CLOSE_CART_LAYER)
        self._wait_for_cart_layer_to_close()
        logger.info("Closed post-add overlay via dialog X button")
        return True

    def _wait_for_cart_layer_to_close(self, timeout_ms: int = 5000) -> None:
        deadline = time.time() + (timeout_ms / 1000.0)

        while time.time() < deadline:
            if not self.is_visible(self.CART_LAYER, timeout_ms=250):
                return
            self.page.wait_for_timeout(100)

        logger.warning("Post-add-to-cart overlay did not disappear within %sms", timeout_ms)
