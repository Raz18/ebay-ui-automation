"""eBay homepage: search, navigation, cookie consent, shipping preference."""

from __future__ import annotations

import allure
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from pages.base_page import BasePage, EL
from utils.logger import get_logger

logger = get_logger(__name__)


COUNTRY_CODES = {
    "united states": {"US", "USA"},
    "israel": {"IL", "ISR"},
}

SHIPPING_IFRAME_SELECTOR = (
    "iframe[title='Shipping Address'][src*='/buyer-preferences/shipping-address']"
)


class HomePage(BasePage):
    # --- Locators ---

    SEARCH_INPUT = EL("Search Input", [
        ("css", "input#gh-ac"),
        ("placeholder", "Search for anything"),
    ])
    SEARCH_BUTTON = EL("Search Button", [
        ("css", "button#gh-search-btn"),
        ("xpath", "//button[@id='gh-search-btn' and @type='submit']"),
    ])
    CATEGORY_DROPDOWN = EL("Category Dropdown", [
        ("css", "select#gh-cat"),
        ("label", "Select a category for search"),
    ])
    SIGN_IN_LINK = EL("Sign In Link", [
        ("text", "Sign in"),
        ("css", "a[href*='signin']"),
    ])
    CART_LINK = EL("Cart Link", [
        ("css", "a[href*='cart.ebay.com']"),
        ("xpath", "//a[contains(@aria-label,'cart')]"),
    ])
    SHOP_BY_CATEGORY = EL("Shop by Category", [
        ("css", "button#gh-shop-a"),
        ("text", "Shop by category"),
    ])
    COOKIE_ACCEPT_BUTTON = EL("Cookie Accept Button", [
        ("css", "button#gdpr-banner-accept"),
        ("text", "Accept"),
    ])
    SHIPPING_POPUP_FRAME = EL("Shipping Popup iFrame", [
        ("css", SHIPPING_IFRAME_SELECTOR),
        (
            "xpath",
            "//iframe[@title='Shipping Address' and contains(@src,'buyer-preferences/shipping-address')]",
        ),
    ])

    # --- Actions ---

    @allure.step("Navigate to eBay homepage")
    def navigate_to_home(self) -> HomePage:
        self.navigate(self._settings.BASE_URL)
        self._dismiss_popups()
        return self

    def search(self, keyword: str) -> None:
        with allure.step(f"Search for '{keyword}'"):
            self.fill(self.SEARCH_INPUT, keyword)
            self.click(self.SEARCH_BUTTON)
            self.wait_for_page_load()

    def _dismiss_popups(self) -> None:
        """Handle popups that appear on page load."""
        cookie_button = self._find_optional(self.COOKIE_ACCEPT_BUTTON, timeout_ms=2500)
        if cookie_button is not None:
            cookie_button.click()
            logger.info("Cookie consent accepted")

        self._confirm_shipping_location()

    def _confirm_shipping_location(self) -> None:
        """Confirm the shipping location popup and select Israel quickly."""
        frame_host = self._find_optional(self.SHIPPING_POPUP_FRAME, timeout_ms=5000)
        if frame_host is None:
            return

        frame = self._page.frame_locator(SHIPPING_IFRAME_SELECTOR)
        self._select_shipping_country(frame)

        zipcode = self._settings.SHIPPING_ZIPCODE
        if zipcode:
            zip_input = self._first_frame_visible(
                frame,
                "input[placeholder*='Zip']",
                "input[aria-label*='Zip']",
                "input[name*='zip']",
                timeout_ms=1500,
            )
            if zip_input is not None:
                zip_input.fill(zipcode)
                logger.info("Entered shipping zipcode: %s", zipcode)

        confirm_button = self._first_frame_visible(
            frame,
            "button:has-text('Confirm')",
            "button:has-text('Done')",
            timeout_ms=3000,
        )
        if confirm_button is None:
            logger.warning("Shipping popup confirm button not found")
            return

        confirm_button.click()
        self._wait_for_shipping_popup_to_close(frame_host)
        logger.info("Shipping location confirmed")

    def _wait_for_shipping_popup_to_close(self, frame_host) -> None:
        try:
            frame_host.wait_for(state="detached", timeout=4000)
            return
        except PlaywrightTimeout:
            pass

        try:
            frame_host.wait_for(state="hidden", timeout=2000)
        except PlaywrightTimeout:
            logger.info("Shipping popup stayed attached after confirmation")

    def _select_shipping_country(self, frame) -> None:
        country = self._settings.SHIPPING_COUNTRY.strip()
        if not country:
            return

        select = self._first_frame_visible(
            frame,
            "select[aria-label*='Country']",
            "select[name*='country']",
            "select[id*='country']",
            "select",
            timeout_ms=3000,
        )
        if select is None:
            logger.warning("Could not find a shipping country selector for '%s'", country)
            return

        try:
            select.select_option(label=country)
            logger.info("Selected shipping country: %s", country)
            return
        except Exception:
            pass

        country_codes = COUNTRY_CODES.get(country.lower(), set())
        try:
            for option in select.locator("option").all():
                label = (option.text_content() or "").strip()
                value = (option.get_attribute("value") or "").strip()
                if country.lower() in label.lower() or value.upper() in country_codes:
                    if value:
                        select.select_option(value=value)
                    else:
                        select.select_option(label=label)
                    logger.info("Selected shipping country: %s", label or country)
                    return
        except Exception as exc:
            logger.warning("Failed to select shipping country '%s': %s", country, exc)
            return

        logger.warning("Could not match a shipping country option for '%s'", country)

    def _first_frame_visible(self, frame, *selectors: str, timeout_ms: int = 1000):
        for selector in selectors:
            locator = frame.locator(selector).first
            try:
                locator.wait_for(state="visible", timeout=timeout_ms)
                return locator
            except PlaywrightTimeout:
                continue
            except Exception:
                continue
        return None

    def go_to_sign_in(self) -> None:
        self.click(self.SIGN_IN_LINK)
        self.wait_for_page_load()

    def go_to_cart(self) -> None:
        from pages.cart_page import CartPage

        CartPage(self.page, self._settings).navigate_to_cart()
