"""Screenshot capture with Allure integration."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from config.settings import Settings
from utils.logger import get_logger


if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = get_logger(__name__)


def capture_screenshot(
    page: Page,
    name: str,
    attach_to_allure: bool = True,
) -> Path:
    """Capture a full-page screenshot and optionally attach to Allure.

    Saves to reports/<run_id>/screenshots/{timestamp}_{name}.png.
    """
    settings = Settings.from_env()
    screenshots_dir = settings.screenshots_path
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize name: replace spaces with underscores
    safe_name = name.replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{safe_name}.png"
    filepath = screenshots_dir / filename

    logger.info(
        "Capturing screenshot: %s (URL: %s)", filename, page.url
    )

    page.screenshot(path=str(filepath), full_page=True)
    logger.info("Screenshot saved to %s", filepath)

    if attach_to_allure:
        _attach_to_allure(filepath, safe_name)

    return filepath


def _attach_to_allure(filepath: Path, name: str) -> None:
    """Attach screenshot to Allure. Silently skips if allure unavailable."""
    try:
        import allure

        allure.attach.file(
            str(filepath),
            name=name,
            attachment_type=allure.attachment_type.PNG,
        )
        logger.debug("Screenshot attached to Allure report: %s", name)
    except ImportError:
        logger.debug("Allure not available — skipping attachment")
    except Exception as exc:
        logger.warning("Failed to attach screenshot to Allure: %s", exc)
