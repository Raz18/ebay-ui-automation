"""Retry handler with exponential backoff for transient action failures.

Provides ``with_retry`` (function wrapper).
Handles action-level retries only — use LocatorEngine for locator
fallback and pytest-rerunfailures for test-level retries.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from config.settings import Settings
from utils.logger import get_logger


logger = get_logger(__name__)


def _get_settings() -> Settings:
    return Settings.from_env()

T = TypeVar("T")


def with_retry(
    action: Callable[[], T],
    *,
    max_retries: int | None = None,
    backoff_factor: float | None = None,
    recoverable_exceptions: tuple[type[BaseException], ...] = (Exception,),
    recovery_action: Callable[[], None] | None = None,
) -> T:
    """Execute *action* with retry and exponential backoff.

    Delay between attempts: ``LOCATOR_ATTEMPT_TIMEOUT * (backoff_factor ** attempt)``.
    If *recovery_action* is provided (e.g. ``page.reload``) it runs before each wait.
    """
    settings = _get_settings()
    retries = max_retries if max_retries is not None else settings.MAX_RETRIES
    factor = backoff_factor if backoff_factor is not None else settings.BACKOFF_FACTOR
    base_ms = settings.LOCATOR_ATTEMPT_TIMEOUT

    action_name = getattr(action, "__name__", repr(action))
    last_exception: BaseException | None = None

    for attempt in range(retries + 1):
        try:
            return action()
        except recoverable_exceptions as exc:
            last_exception = exc

            if attempt == retries:
                # Final attempt failed — no more retries
                break

            delay_ms = base_ms * (factor ** attempt)
            delay_s = delay_ms / 1000

            logger.warning(
                "Retry %d/%d for '%s' — waiting %.0fms (reason: %s)",
                attempt + 1, retries, action_name, delay_ms, exc,
            )

            if recovery_action is not None:
                try:
                    recovery_action()
                except Exception as rec_exc:
                    logger.warning(
                        "Recovery action failed during retry: %s", rec_exc,
                    )

            # Backoff — time.sleep is acceptable in sync Playwright context
            time.sleep(delay_s)

    # All retries exhausted
    logger.error(
        "All %d retries exhausted for '%s': %s",
        retries, action_name, last_exception,
    )
    raise last_exception  # type: ignore[misc]

