"""eBay login page — multi-step sign-in flow with CAPTCHA detection."""

from __future__ import annotations

import allure

from pages.base_page import BasePage, EL
from utils.logger import get_logger

logger = get_logger(__name__)


class CaptchaBlockedError(Exception):
    """Raised when a CAPTCHA blocks automated interaction."""


class LoginPage(BasePage):

    # --- Locators ---

    EMAIL_INPUT = EL("Email Input", [
        ("css", "input#userid"),
        ("label", "Email or username"),
    ])
    CONTINUE_BUTTON = EL("Continue Button", [
        ("css", "button#signin-continue-btn"),
        ("text", "Continue"),
    ])
    PASSWORD_INPUT = EL("Password Input", [
        ("css", "input#pass"),
        ("label", "Password"),
    ])
    SIGN_IN_BUTTON = EL("Sign In Submit Button", [
        ("css", "button#sgnBt"),
        ("text", "Sign in"),
    ])
    CAPTCHA_FRAME = EL("CAPTCHA Frame", [
        ("css", "iframe[title*='challenge']"),
        ("xpath", "//iframe[contains(@src,'captcha')]"),
    ])
    ERROR_MESSAGE = EL("Login Error Message", [
        ("css", "#signin-error-msg"),
        ("xpath", "//p[@id='signin-error-msg']"),
    ])
    GOOGLE_OVERLAY_DISMISS = EL("Google Overlay Dismiss", [
        ("label", "Close"),
        ("css", "button[aria-label='Close']"),
    ])

    # --- Actions ---

    @allure.step("Navigate to eBay sign-in page")
    def navigate_to_login(self) -> LoginPage:
        self.navigate(f"{self._settings.BASE_URL}/signin")
        self._dismiss_google_overlay()
        return self

    def enter_email(self, email: str) -> None:
        with allure.step(f"Enter email '{email}'"):
            self.fill(self.EMAIL_INPUT, email)
            self.click(self.CONTINUE_BUTTON)
            self.wait_for_page_load()

    @allure.step("Enter password")
    def enter_password(self, password: str) -> None:
        self.fill(self.PASSWORD_INPUT, password)

    @allure.step("Submit sign-in form")
    def click_sign_in(self) -> None:
        self.click(self.SIGN_IN_BUTTON)
        self.wait_for_page_load()

    def is_captcha_present(self) -> bool:
        return self.is_visible(self.CAPTCHA_FRAME, timeout_ms=3000)

    def check_captcha_and_raise(self) -> None:
        """Raise CaptchaBlockedError if CAPTCHA is detected."""
        if self.is_captcha_present():
            self.take_screenshot("captcha_detected")
            raise CaptchaBlockedError("CAPTCHA detected — manual intervention required")

    def _dismiss_google_overlay(self) -> None:
        if self.is_visible(self.GOOGLE_OVERLAY_DISMISS, timeout_ms=2000):
            self.click(self.GOOGLE_OVERLAY_DISMISS)
            logger.info("Dismissed Google sign-in overlay")
