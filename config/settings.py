"""Central configuration loader — env-var overrides via python-dotenv."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv


# Load .env file from project root if it exists
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _sanitize_run_label(label: str) -> str:
    """Convert a free-form run label into a compact filesystem-safe token."""
    sanitized = "".join(char if char.isalnum() else "_" for char in label.strip().lower())
    sanitized = "_".join(filter(None, sanitized.split("_")))
    return sanitized[:48]


def _default_run_id(label: str | None = None) -> str:
    """Generate a run id that stays stable within a process and unique across runs."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_label = _sanitize_run_label(label or "")
    if safe_label:
        return f"{timestamp}_{safe_label}_{uuid4().hex[:8]}"
    return f"{timestamp}_{uuid4().hex[:8]}"


_DEFAULT_RUN_LABEL = _sanitize_run_label(os.getenv("RUN_LABEL", ""))
_DEFAULT_RUN_ID = os.getenv("RUN_ID") or _default_run_id(_DEFAULT_RUN_LABEL)


def _env_str(key: str, default: str) -> str:
    """Read a string from environment or return default."""
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    """Read an integer from environment or return default."""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    """Read a float from environment or return default."""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    """Read a boolean from environment or return default.

    Truthy values: "1", "true", "yes" (case-insensitive).
    """
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class Settings:
    """Immutable project-wide settings with environment variable overrides."""

    BASE_URL: str = "https://www.ebay.com"
    DEFAULT_TIMEOUT: int = 30000
    LOCATOR_ATTEMPT_TIMEOUT: int = 5000
    MAX_RETRIES: int = 3
    BACKOFF_FACTOR: float = 2.0
    SCREENSHOT_ON_FAILURE: bool = True
    REPORTS_DIR: str = "reports"
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = ""
    HEADLESS: bool = False
    BROWSER: str = "chromium"
    BROWSER_CHANNEL: str = "chrome"
    SLOW_MO: int = 0
    MASK_AUTOMATION: bool = True
    BROWSER_LOCALE: str = "en-US"
    TIMEZONE_ID: str = "America/New_York"
    ACCEPT_LANGUAGE: str = "en-US,en;q=0.9"
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    STORAGE_STATE_PATH: str = ""
    SAVE_STORAGE_STATE_PATH: str = ""
    PREFERRED_CURRENCY: str = "ILS"
    STRICT_CURRENCY_VALIDATION: bool = False
    SHIPPING_COUNTRY: str = "Israel"
    SHIPPING_ZIPCODE: str = ""
    ANTI_BOT_DELAY_MIN: float = 1.5
    ANTI_BOT_DELAY_MAX: float = 4.0
    RUN_LABEL: str = _DEFAULT_RUN_LABEL
    RUN_ID: str = _DEFAULT_RUN_ID
    TRACE_ENABLED: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        """Create a Settings instance with values from environment variables."""
        return cls(
            BASE_URL=_env_str("EBAY_BASE_URL", cls.BASE_URL),
            DEFAULT_TIMEOUT=_env_int("DEFAULT_TIMEOUT", cls.DEFAULT_TIMEOUT),
            LOCATOR_ATTEMPT_TIMEOUT=_env_int(
                "LOCATOR_ATTEMPT_TIMEOUT", cls.LOCATOR_ATTEMPT_TIMEOUT
            ),
            MAX_RETRIES=_env_int("MAX_RETRIES", cls.MAX_RETRIES),
            BACKOFF_FACTOR=_env_float("BACKOFF_FACTOR", cls.BACKOFF_FACTOR),
            SCREENSHOT_ON_FAILURE=_env_bool(
                "SCREENSHOT_ON_FAILURE", cls.SCREENSHOT_ON_FAILURE
            ),
            REPORTS_DIR=_env_str("REPORTS_DIR", cls.REPORTS_DIR),
            LOG_LEVEL=_env_str("LOG_LEVEL", cls.LOG_LEVEL),
            LOG_FILE=_env_str("LOG_FILE", cls.LOG_FILE),
            HEADLESS=_env_bool("HEADLESS", cls.HEADLESS),
            BROWSER=_env_str("BROWSER", cls.BROWSER),
            BROWSER_CHANNEL=_env_str("BROWSER_CHANNEL", cls.BROWSER_CHANNEL),
            SLOW_MO=_env_int("SLOW_MO", cls.SLOW_MO),
            MASK_AUTOMATION=_env_bool("MASK_AUTOMATION", cls.MASK_AUTOMATION),
            BROWSER_LOCALE=_env_str("BROWSER_LOCALE", cls.BROWSER_LOCALE),
            TIMEZONE_ID=_env_str("TIMEZONE_ID", cls.TIMEZONE_ID),
            ACCEPT_LANGUAGE=_env_str("ACCEPT_LANGUAGE", cls.ACCEPT_LANGUAGE),
            USER_AGENT=_env_str("USER_AGENT", cls.USER_AGENT),
            STORAGE_STATE_PATH=_env_str("STORAGE_STATE_PATH", cls.STORAGE_STATE_PATH),
            SAVE_STORAGE_STATE_PATH=_env_str(
                "SAVE_STORAGE_STATE_PATH",
                cls.SAVE_STORAGE_STATE_PATH,
            ),
            PREFERRED_CURRENCY=_env_str("PREFERRED_CURRENCY", cls.PREFERRED_CURRENCY),
            STRICT_CURRENCY_VALIDATION=_env_bool(
                "STRICT_CURRENCY_VALIDATION",
                cls.STRICT_CURRENCY_VALIDATION,
            ),
            SHIPPING_COUNTRY=_env_str("SHIPPING_COUNTRY", cls.SHIPPING_COUNTRY),
            SHIPPING_ZIPCODE=_env_str("SHIPPING_ZIPCODE", cls.SHIPPING_ZIPCODE),
            ANTI_BOT_DELAY_MIN=_env_float("ANTI_BOT_DELAY_MIN", cls.ANTI_BOT_DELAY_MIN),
            ANTI_BOT_DELAY_MAX=_env_float("ANTI_BOT_DELAY_MAX", cls.ANTI_BOT_DELAY_MAX),
            RUN_LABEL=_sanitize_run_label(_env_str("RUN_LABEL", cls.RUN_LABEL)),
            RUN_ID=_env_str("RUN_ID", cls.RUN_ID),
            TRACE_ENABLED=_env_bool("PLAYWRIGHT_TRACE", cls.TRACE_ENABLED),
        )

    @property
    def project_root(self) -> Path:
        """Return the resolved project root directory."""
        return Path(__file__).resolve().parent.parent

    @property
    def reports_path(self) -> Path:
        """Return the resolved reports directory path."""
        return self.project_root / self.REPORTS_DIR

    @property
    def run_reports_path(self) -> Path:
        """Return a timestamped subdirectory for this specific test run."""
        return self.reports_path / self.RUN_ID

    @property
    def allure_results_path(self) -> Path:
        """Return the Allure raw results path for this specific test run."""
        return self.run_reports_path / "allure-results"

    @property
    def screenshots_path(self) -> Path:
        """Return the resolved screenshots directory path."""
        return self.run_reports_path / "screenshots"

    @property
    def traces_path(self) -> Path:
        """Return the Playwright traces path for this specific test run."""
        return self.run_reports_path / "traces"
