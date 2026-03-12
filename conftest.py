"""Root conftest — browser lifecycle, Allure hooks, screenshot on failure."""

from __future__ import annotations

import os
from pathlib import Path

import allure
import pytest
from playwright.sync_api import sync_playwright
from playwright.sync_api import Error as PlaywrightError

from config.browser_profiles import BROWSER_MATRIX, get_browser_profile
from config.settings import Settings, _default_run_id, _sanitize_run_label
from utils.screenshot_helper import capture_screenshot


def pytest_addoption(parser):
    """Register CLI options for browser profile selection and report behavior."""
    parser.addoption(
        "--browser-profile",
        action="store",
        default=None,
        help="Run tests against a single browser profile (chrome, msedge, firefox).",
    )
    parser.addoption(
        "--pw-trace",
        action="store_true",
        default=False,
        help="Enable Playwright trace capture for debug runs.",
    )
    parser.addoption(
        "--run-label",
        action="store",
        default=None,
        help="Readable label to include in the per-run reports directory name.",
    )
    parser.addoption(
        "--storage-state",
        action="store",
        default=None,
        help="Path to a Playwright storage-state JSON file to preload into each browser context.",
    )
    parser.addoption(
        "--save-storage-state",
        action="store",
        default=None,
        help="Path to save the current Playwright storage state at fixture teardown.",
    )


def _derive_run_label(config) -> str:
    """Return a readable label for the current pytest invocation."""
    explicit_label = config.getoption("--run-label")
    if explicit_label:
        return _sanitize_run_label(explicit_label) or "test_run"

    invocation_args = list(getattr(config, "args", ()) or ())
    targets = [arg for arg in invocation_args if arg and not str(arg).startswith("-")]
    if not targets:
        return "full_suite"

    first_target = str(targets[0]).strip()
    primary_target = first_target.split("::", 1)[0].rstrip("\\/")
    stem = Path(primary_target).stem or primary_target or "test_run"

    if len(targets) > 1:
        return _sanitize_run_label(f"{stem}_and_more") or "multi_target"
    return _sanitize_run_label(stem) or "test_run"


def pytest_configure(config):
    """Register markers and route Allure output into a run-scoped directory."""
    config.addinivalue_line(
        "markers",
        "browser_matrix: parametrize test across all browser profiles",
    )
    run_label = _sanitize_run_label(os.getenv("RUN_LABEL", "")) or _derive_run_label(config)
    os.environ.setdefault("RUN_LABEL", run_label)
    os.environ.setdefault("RUN_ID", _default_run_id(run_label))
    if config.getoption("--storage-state"):
        os.environ.setdefault("STORAGE_STATE_PATH", config.getoption("--storage-state"))
    if config.getoption("--save-storage-state"):
        os.environ.setdefault(
            "SAVE_STORAGE_STATE_PATH",
            config.getoption("--save-storage-state"),
        )

    settings = Settings.from_env()
    settings.run_reports_path.mkdir(parents=True, exist_ok=True)

    if not getattr(config.option, "allure_report_dir", None):
        config.option.allure_report_dir = str(settings.allure_results_path)
    if getattr(config.option, "allure_report_dir", None):
        os.makedirs(config.option.allure_report_dir, exist_ok=True)


def pytest_report_header(config):
    """Show the active run-scoped report directory in pytest output."""
    settings = Settings.from_env()
    return [
        f"run reports dir: {settings.run_reports_path}",
        f"run label: {settings.RUN_LABEL or 'n/a'}",
    ]


def _resolve_profiles(config) -> list[dict]:
    """Return the list of browser profiles to run against."""
    name = config.getoption("--browser-profile")
    if name:
        return [get_browser_profile(name)]
    return BROWSER_MATRIX


@pytest.fixture(scope="session")
def settings():
    """Project-wide settings, resolved once per session."""
    return Settings.from_env()


@pytest.fixture(scope="session", params=None)
def browser_profile(request, settings):
    """Yield a browser profile dict. Parametrized dynamically by the hook below."""
    return request.param


def pytest_generate_tests(metafunc):
    """Parametrize the browser_profile fixture across the resolved matrix."""
    if "browser_profile" not in metafunc.fixturenames:
        return

    profiles = _resolve_profiles(metafunc.config)
    metafunc.parametrize(
        "browser_profile",
        profiles,
        ids=[p["name"] for p in profiles],
        indirect=True,
        scope="session",
    )


@pytest.fixture(scope="session")
def browser(settings):
    """Launch a single browser (default profile) for non-matrix tests."""
    with sync_playwright() as pw:
        pw.selectors.set_test_id_attribute("data-test-id")
        browser_type = getattr(pw, settings.BROWSER)
        launch_args = _build_launch_args(settings.HEADLESS, settings.SLOW_MO, settings.BROWSER_CHANNEL, settings.BROWSER)
        browser = browser_type.launch(**launch_args)
        yield browser
        browser.close()


@pytest.fixture(scope="session")
def matrix_browser(browser_profile, settings):
    """Launch a browser for each matrix profile."""
    profile = browser_profile
    with sync_playwright() as pw:
        pw.selectors.set_test_id_attribute("data-test-id")
        browser_type = getattr(pw, profile["browser"])
        launch_args = _build_launch_args(
            profile.get("headless", settings.HEADLESS),
            settings.SLOW_MO,
            profile.get("channel"),
            profile["browser"],
        )
        browser = browser_type.launch(**launch_args)
        yield browser
        browser.close()


def _build_launch_args(headless: bool, slow_mo: int, channel: str | None, browser_name: str = "chromium") -> dict:
    args = {
        "headless": headless,
        "slow_mo": slow_mo,
    }
    if browser_name != "firefox":
        args["args"] = [
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
        ]
    if channel:
        args["channel"] = channel
    return args


def _new_context(browser, settings):
    """Create a browser context with anti-detection fingerprint defaults."""
    context_kwargs = {
        "viewport": {"width": 1920, "height": 1080},
        "base_url": settings.BASE_URL,
        "locale": settings.BROWSER_LOCALE,
        "timezone_id": settings.TIMEZONE_ID,
        "extra_http_headers": {
            "Accept-Language": settings.ACCEPT_LANGUAGE,
        },
    }

    if settings.USER_AGENT:
        context_kwargs["user_agent"] = settings.USER_AGENT
    if settings.STORAGE_STATE_PATH:
        storage_state_path = Path(settings.STORAGE_STATE_PATH)
        if storage_state_path.exists():
            context_kwargs["storage_state"] = str(storage_state_path)

    ctx = browser.new_context(**context_kwargs)
    if settings.MASK_AUTOMATION:
        # Optional only. Some live sites treat spoofed automation fingerprints as higher risk.
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    ctx.set_default_timeout(settings.DEFAULT_TIMEOUT)
    return ctx


@pytest.fixture()
def trace_enabled(pytestconfig, settings):
    """Return True when Playwright tracing is explicitly enabled."""
    return pytestconfig.getoption("--pw-trace") or settings.TRACE_ENABLED


@pytest.fixture()
def context(browser, settings, trace_enabled):
    """Fresh browser context per test (default single browser) with optional trace capture."""
    ctx = _new_context(browser, settings)
    if trace_enabled:
        ctx.tracing.start(screenshots=True, snapshots=True, sources=True)
    yield ctx
    if trace_enabled:
        try:
            trace_path = settings.traces_path / f"trace_{id(ctx)}.zip"
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            ctx.tracing.stop(path=str(trace_path))
        except Exception:
            pass
    if settings.SAVE_STORAGE_STATE_PATH:
        storage_state_path = Path(settings.SAVE_STORAGE_STATE_PATH)
        storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            ctx.storage_state(path=str(storage_state_path))
        except Exception:
            pass
    try:
        ctx.close()
    except PlaywrightError:
        pass


@pytest.fixture()
def matrix_context(matrix_browser, settings, trace_enabled):
    """Fresh browser context per test (matrix browser) with optional trace capture."""
    ctx = _new_context(matrix_browser, settings)
    if trace_enabled:
        ctx.tracing.start(screenshots=True, snapshots=True, sources=True)
    yield ctx
    if trace_enabled:
        try:
            trace_path = settings.traces_path / f"trace_{id(ctx)}.zip"
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            ctx.tracing.stop(path=str(trace_path))
        except Exception:
            pass
    if settings.SAVE_STORAGE_STATE_PATH:
        storage_state_path = Path(settings.SAVE_STORAGE_STATE_PATH)
        storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            ctx.storage_state(path=str(storage_state_path))
        except Exception:
            pass
    try:
        ctx.close()
    except PlaywrightError:
        pass


@pytest.fixture()
def page(context):
    """Fresh page per test."""
    pg = context.new_page()
    yield pg
    if pg.is_closed():
        return
    try:
        pg.close(run_before_unload=False)
    except PlaywrightError:
        pass


@pytest.fixture()
def matrix_page(matrix_context):
    """Fresh page per test (matrix browser)."""
    pg = matrix_context.new_page()
    yield pg
    if pg.is_closed():
        return
    try:
        pg.close(run_before_unload=False)
    except PlaywrightError:
        pass


# --- Allure hooks: screenshot + page URL on failure ---

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach screenshot and page URL to Allure on test failure."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        pg = item.funcargs.get("page") or item.funcargs.get("matrix_page")
        if pg and not pg.is_closed():
            screenshot_name = _safe_artifact_name(item.nodeid)
            screenshot_path = capture_screenshot(
                pg,
                f"failure_{screenshot_name}",
                attach_to_allure=False,
            )
            allure.attach(
                screenshot_path.read_bytes(),
                name="failure_screenshot",
                attachment_type=allure.attachment_type.PNG,
            )
            allure.attach(
                pg.url,
                name="failure_url",
                attachment_type=allure.attachment_type.TEXT,
            )


def _safe_artifact_name(value: str) -> str:
    sanitized = "".join(char if char.isalnum() else "_" for char in value)
    return sanitized.strip("_") or "test"
