"""Login orchestration — composes LoginPage into a complete sign-in flow."""

from __future__ import annotations

from typing import TYPE_CHECKING

import allure
import pytest

from pages.login_page import CaptchaBlockedError, LoginPage
from utils.logger import get_logger

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = get_logger(__name__)


@allure.step("Login as '{username}'")
def login(page: Page, username: str, password: str) -> None:
    """Full eBay login flow: email → continue → password → sign in.

    Skips the test if CAPTCHA is detected at any step.
    """
    login_page = LoginPage(page)
    login_page.navigate_to_login()

    try:
        login_page.check_captcha_and_raise()
        login_page.enter_email(username)

        login_page.check_captcha_and_raise()
        login_page.enter_password(password)
        login_page.click_sign_in()

        login_page.check_captcha_and_raise()
    except CaptchaBlockedError as exc:
        pytest.skip(str(exc))

    logger.info("Login completed for '%s'", username)
