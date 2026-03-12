"""Smart locator fallback engine.

Each UI element is defined with multiple locator strategies. The engine
tries each in order, stops at first success, and logs every attempt.
This is the only module that calls page.locator() or page.get_by_*().
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from config.settings import Settings
from utils.logger import get_logger
from utils.screenshot_helper import capture_screenshot


if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page


logger = get_logger(__name__)


class ElementNotFoundError(Exception):
    """Raised when all locator strategies for an element have been exhausted."""

    def __init__(
        self,
        element_name: str,
        tried_locators: list[tuple[str, str]],
        screenshot_path: str | None = None,
    ) -> None:
        self.element_name = element_name
        self.tried_locators = tried_locators
        self.screenshot_path = screenshot_path

        details = "\n".join(
            f"  {i + 1}. {strategy}={value}"
            for i, (strategy, value) in enumerate(tried_locators)
        )
        msg = (
            f"All {len(tried_locators)} locators failed for '{element_name}'.\n"
            f"Tried:\n{details}"
        )
        if screenshot_path:
            msg += f"\nScreenshot: {screenshot_path}"

        super().__init__(msg)


@dataclass(frozen=True)
class ElementLocators:
    """Multiple locator strategies for a single UI element.

    Minimum 2 locators required, mixing different approaches for resilience.
    Supported strategies: css, xpath, text, role, test_id, placeholder, label.
    """

    name: str
    locators: list[tuple[str, str]]

    def __post_init__(self) -> None:
        if len(self.locators) < 2:
            raise ValueError(
                f"ElementLocators '{self.name}' requires at least 2 locators, "
                f"got {len(self.locators)}"
            )


class LocatorEngine:
    """Resilient element finder with ordered multi-locator fallback.

    Consumed exclusively by BasePage. Optional lookups return ``None`` without
    screenshots; required lookups still log every failure and capture evidence.
    """

    def __init__(
        self,
        page: Page,
        settings: Settings | None = None,
    ) -> None:
        self._page = page
        self._settings = settings or Settings.from_env()

    # --- Public API ---

    def find(
        self,
        element: ElementLocators,
        timeout_ms: int | None = None,
    ) -> Locator:
        """Find a single visible element, raising on final failure."""
        locator = self.find_optional(element, timeout_ms=timeout_ms)
        if locator is not None:
            return locator

        total = len(element.locators)
        for idx, (strategy, value) in enumerate(element.locators, start=1):
            logger.warning(
                "FAIL '%s': locator %d/%d failed - %s=%s",
                element.name,
                idx,
                total,
                strategy,
                value,
            )

        return self._raise_not_found(element)

    def find_all(
        self,
        element: ElementLocators,
        timeout_ms: int | None = None,
    ) -> Locator:
        """Find multiple elements, raising on final failure."""
        locator = self.find_all_optional(element, timeout_ms=timeout_ms)
        if locator is not None:
            return locator

        total = len(element.locators)
        for idx, (strategy, value) in enumerate(element.locators, start=1):
            logger.warning(
                "FAIL '%s': locator %d/%d found 0 elements - %s=%s",
                element.name,
                idx,
                total,
                strategy,
                value,
            )

        return self._raise_not_found(element)

    def find_optional(
        self,
        element: ElementLocators,
        timeout_ms: int | None = None,
    ) -> Locator | None:
        """Find a single visible element without treating absence as a failure."""
        return self._poll_locators(
            element,
            timeout_ms=timeout_ms,
            state="visible",
            expect_multiple=False,
        )

    def find_all_optional(
        self,
        element: ElementLocators,
        timeout_ms: int | None = None,
    ) -> Locator | None:
        """Find multiple elements without treating absence as a failure."""
        return self._poll_locators(
            element,
            timeout_ms=timeout_ms,
            state="attached",
            expect_multiple=True,
        )

    def peek_optional(
        self,
        element: ElementLocators,
        timeout_ms: int = 500,
    ) -> Locator | None:
        """Quickly probe for a visible element without paying full optional wait cost."""
        return self._peek_locators(
            element,
            timeout_ms=timeout_ms,
            expect_multiple=False,
        )

    def peek_all_optional(
        self,
        element: ElementLocators,
        timeout_ms: int = 500,
    ) -> Locator | None:
        """Quickly probe for attached elements without paying full optional wait cost."""
        return self._peek_locators(
            element,
            timeout_ms=timeout_ms,
            expect_multiple=True,
        )

    # --- Internal helpers ---

    def _poll_locators(
        self,
        element: ElementLocators,
        *,
        timeout_ms: int | None,
        state: str,
        expect_multiple: bool,
    ) -> Locator | None:
        timeout = timeout_ms or self._settings.LOCATOR_ATTEMPT_TIMEOUT
        total = len(element.locators)
        end_time = time.time() + (timeout / 1000.0)
        # Give each strategy a reasonable chunk of the timeout
        poll_timeout = max(1, min(1000, timeout))

        while time.time() < end_time:
            for idx, (strategy, value) in enumerate(element.locators, start=1):
                locator = self._resolve(strategy, value)
                try:
                    locator.first.wait_for(state=state, timeout=poll_timeout)
                    if expect_multiple:
                        count = locator.count()
                        if count == 0:
                            continue
                        logger.info(
                            "OK '%s': locator %d/%d found %d elements - %s=%s",
                            element.name,
                            idx,
                            total,
                            count,
                            strategy,
                            value,
                        )
                        return locator

                    logger.info(
                        "OK '%s': locator %d/%d succeeded - %s=%s",
                        element.name,
                        idx,
                        total,
                        strategy,
                        value,
                    )
                    return locator.first
                except PlaywrightTimeout:
                    continue

        logger.info("Optional element '%s' was not found", element.name)
        return None

    def _peek_locators(
        self,
        element: ElementLocators,
        *,
        timeout_ms: int,
        expect_multiple: bool,
    ) -> Locator | None:
        """Perform a short, non-blocking probe for optional elements."""
        end_time = time.time() + (timeout_ms / 1000.0)

        while time.time() < end_time:
            for strategy, value in element.locators:
                locator = self._resolve(strategy, value)
                try:
                    if locator.count() == 0:
                        continue
                    if expect_multiple:
                        return locator
                    if locator.first.is_visible():
                        return locator.first
                except Exception:
                    continue
            time.sleep(0.05)

        return None

    def _resolve(self, strategy: str, value: str) -> Locator:
        """Map a (strategy, value) pair to a Playwright Locator."""
        match strategy:
            case "css" | "xpath":
                return self._page.locator(value)
            case "text":
                return self._page.get_by_text(value)
            case "role":
                return self._page.get_by_role(value)
            case "test_id":
                return self._page.get_by_test_id(value)
            case "placeholder":
                return self._page.get_by_placeholder(value)
            case "label":
                return self._page.get_by_label(value)
            case _:
                raise ValueError(
                    f"Unknown locator strategy '{strategy}'. "
                    f"Supported: css, xpath, text, role, test_id, placeholder, label"
                )

    def _raise_not_found(self, element: ElementLocators) -> Locator:
        """Capture screenshot and raise ElementNotFoundError."""
        screenshot_path: str | None = None
        try:
            path = capture_screenshot(
                self._page,
                f"{element.name}_all_locators_failed",
            )
            screenshot_path = str(path)
        except Exception as exc:
            logger.warning("Could not capture failure screenshot: %s", exc)

        logger.error(
            "All %d locators failed for '%s'",
            len(element.locators),
            element.name,
        )
        raise ElementNotFoundError(
            element_name=element.name,
            tried_locators=element.locators,
            screenshot_path=screenshot_path,
        )
