"""Unit tests for the login flow using MagicMock."""

from unittest.mock import MagicMock

import allure
import pytest

import functions.login as login_module
from functions.login import login
from pages.login_page import CaptchaBlockedError


@allure.suite("Unit Tests")
@allure.story("Login Flow")
@allure.severity(allure.severity_level.CRITICAL)
def test_login_flow_success_calls_correct_methods(monkeypatch):
    """Verify that the login function correctly sequences the LoginPage methods."""
    # 1. Create a fake Playwright page (MagicMock handles all attribute accesses without throwing errors)
    page = MagicMock()
    
    # 2. Create a fake LoginPage instance
    fake_login_page = MagicMock()
    
    # 3. Patch the LoginPage class inside functions.login so it returns our fake instance instead of the real one
    monkeypatch.setattr(login_module, "LoginPage", lambda _: fake_login_page)

    # 4. Trigger the function purely in Python (no browser will open)
    login(page, "fakeuser@example.com", "fakepassword123")

    # 5. Assert the flow worked precisely as we expect
    fake_login_page.navigate_to_login.assert_called_once()
    
    # We call captcha check 3 times in the current implementation
    assert fake_login_page.check_captcha_and_raise.call_count == 3
    
    # Assert data was passed correctly
    fake_login_page.enter_email.assert_called_once_with("fakeuser@example.com")
    fake_login_page.enter_password.assert_called_once_with("fakepassword123")
    fake_login_page.click_sign_in.assert_called_once()


@allure.suite("Unit Tests")
@allure.story("Login Flow")
@allure.severity(allure.severity_level.NORMAL)
def test_login_aborts_immediately_on_first_captcha(monkeypatch):
    """Verify that the login function halts if a CAPTCHA is detected early."""
    page = MagicMock()
    fake_login_page = MagicMock()
    
    # Simulate check_captcha_and_raise raising CaptchaBlockedError (which login() converts to pytest.skip)
    fake_login_page.check_captcha_and_raise.side_effect = CaptchaBlockedError("CAPTCHA detected")
    
    monkeypatch.setattr(login_module, "LoginPage", lambda _: fake_login_page)

    # 4. Expect the skip exception to bubble up (login() catches CaptchaBlockedError and calls pytest.skip)
    with pytest.raises(pytest.skip.Exception):
        login(page, "user", "pass")

    # 5. Verify the flow stopped immediately! Methods after the first captcha check should never be called.
    fake_login_page.navigate_to_login.assert_called_once()
    fake_login_page.check_captcha_and_raise.assert_called_once() # Only called once instead of 3 times!
    
    # Ensure it didn't try to type emails or passwords
    fake_login_page.enter_email.assert_not_called()
    fake_login_page.enter_password.assert_not_called()
    fake_login_page.click_sign_in.assert_not_called()
