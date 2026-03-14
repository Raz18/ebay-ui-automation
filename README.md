# eBay E2E Automation Framework

Python-based Playwright automation for live eBay flows:
- search by keyword
- filter by maximum price
- collect result URLs under budget
- add items to cart with variant handling
- verify cart subtotal stays within budget
- cover login with CAPTCHA-aware handling

The framework is built around Page Object Model, a centralized multi-locator engine, pytest execution, and Allure reporting.

## What This Project Implements

Primary E2E scenario:
- search for products on eBay
- apply a max-price constraint
- collect up to `limit` matching product URLs
- open product pages and add items to cart
- randomly choose supported variants when required
- verify the cart subtotal does not exceed `budget_per_item * items_added`

Main E2E entry point:
- `tests/test_e2e_full_flow.py`

Core workflow functions:
- `functions/search.py`
- `functions/cart_actions.py`
- `functions/login.py`

Additional focused test coverage:
- `tests/test_login_unit.py` checks login workflow behavior and CAPTCHA-aware branching
- `tests/test_product_page.py` checks variant selection and post-add-to-cart modal handling
- `tests/test_search.py` checks supporting search behavior outside the main E2E path

## Architecture

```text
tests/
  -> functions/
     -> pages/
        -> BasePage
           -> LocatorEngine + RetryHandler + ScreenshotHelper + PriceParser
```

### Playwright Architecture

The framework uses a layered Playwright lifecycle managed entirely through pytest fixtures:

```text
sync_playwright  (session)
  -> Browser      (session, one launch per profile)
     -> Context   (per-test, isolated cookies/storage/fingerprint)
        -> Page   (per-test, main tab)
           -> Product tab  (reused within add-to-cart loop)
```

Key design decisions:
- **Session-scoped browser** — a single browser process is launched once and shared across all tests in a session, avoiding repeated startup cost
- **Per-test context isolation** — each test gets a fresh `BrowserContext` with its own cookies, storage state, viewport, locale, timezone, and user agent, so tests cannot leak state to each other
- **Anti-detection init scripts** — `navigator.webdriver` is patched via `context.add_init_script()` when `MASK_AUTOMATION` is enabled
- **Custom `data-test-id` attribute** — `pw.selectors.set_test_id_attribute("data-test-id")` is set at session start so `get_by_test_id()` calls target eBay's actual attribute
- **Tab reuse over tab churn** — the add-to-cart flow opens one product tab and navigates it for each item rather than creating/destroying tabs per URL
- **Playwright-native waits** — `page.wait_for_timeout()` is used instead of `time.sleep()` so the browser event loop stays active during delays
- **Opt-in tracing** — `context.tracing.start()` is activated only with `--pw-trace` to keep normal runs lightweight
- **Storage state round-trip** — contexts can load a pre-authenticated state on creation and save the updated state at teardown
- **Cross-browser matrix** — `pytest_generate_tests` dynamically parametrizes the `browser_profile` fixture across Chrome, Edge, and Firefox using `config/browser_profiles.py`

### Project Layout

```text
ebay-ui-automation/
|-- config/
|   |-- browser_profiles.py
|   `-- settings.py
|-- data/
|   |-- search_data.json
|   `-- test_data.json
|-- functions/
|   |-- cart_actions.py
|   |-- login.py
|   `-- search.py
|-- pages/
|   |-- base_page.py
|   |-- cart_page.py
|   |-- home_page.py
|   |-- login_page.py
|   |-- product_page.py
|   `-- search_results_page.py
|-- tests/
|   |-- test_e2e_full_flow.py
|   |-- test_search.py
|   |-- test_login_unit.py
|   |-- test_product_page.py
|   `-- conftest.py
|-- utils/
|   |-- data_loader.py
|   |-- locator_engine.py
|   |-- logger.py
|   |-- price_parser.py
|   |-- retry_handler.py
|   `-- screenshot_helper.py
|-- .github/workflows/e2e.yml
|-- conftest.py
|-- pytest.ini
`-- requirements.txt
```

## Technical Implementation Highlights

### 1. Page Object Model with a thin test layer

Tests only call business workflows or page-level methods. Raw locators are encapsulated inside page objects.

Key classes:
- `pages/base_page.py`
- `pages/search_results_page.py`
- `pages/product_page.py`
- `pages/cart_page.py`
- `pages/login_page.py`

### 2. Centralized resilient locator engine

`utils/locator_engine.py` is the single place that resolves Playwright locators.

Capabilities:
- every critical element is defined with at least 2 locator strategies
- ordered fallback across `css`, `xpath`, `text`, `role`, `test_id`, `placeholder`, and `label`
- required lookups raise `ElementNotFoundError`
- optional lookups return `None` without failing the test
- final failure captures a screenshot
- fast `peek_optional()` / `peek_all_optional()` probes are used for quicker variant discovery

This means fallback logic lives in the framework, not in tests.

### 3. Retry and recovery strategy

`utils/retry_handler.py` wraps transient actions with configurable retries and exponential backoff.

Current behavior:
- retries are driven by `MAX_RETRIES`
- delay uses `LOCATOR_ATTEMPT_TIMEOUT * BACKOFF_FACTOR ** attempt`
- optional `recovery_action` can run before the next retry

### 4. Search flow implementation

`functions/search.py` implements the search workflow.

Important details:
- home preferences are initialized once per Playwright `Page` using a `WeakSet`
- search results are opened directly with a search URL
- the UI max-price filter is applied when available
- the workflow falls back to `_udhi=<max_price>` URL rewriting when needed
- results are collected page by page until the requested `limit` is reached
- duplicate URLs are suppressed and pagination loops are detected

### 5. Add-to-cart orchestration

`functions/cart_actions.py` implements the item-add flow.

Current behavior:
- a single reusable product tab is opened once and shared across all items — avoids the overhead of creating and destroying a tab per URL
- navigating to the next product URL implicitly dismisses any post-add-to-cart modal, eliminating explicit overlay wait/close cycles
- inter-item anti-bot delay uses `page.wait_for_timeout()` instead of `time.sleep()`, keeping the browser event loop active
- the search tab is never touched during the add-to-cart loop since all product work happens in the separate tab
- per-item screenshots are captured after successful add-to-cart
- failures capture dedicated evidence and continue to the next URL
- for CI runs, set `ANTI_BOT_DELAY_MIN=0` and `ANTI_BOT_DELAY_MAX=0` to skip inter-item delays entirely

### 6. Product page variant handling

`pages/product_page.py` contains the variant logic.

Supported variant types:
- dropdown selectors such as size or color
- generic select boxes
- custom listbox controls
- button-based swatches / size groups
- quantity input

Implementation details:
- a fast presence probe runs first so missing variant families do not consume full optional timeouts
- valid options are filtered before random choice
- disabled and placeholder options are skipped
- quantity is randomized when a quantity input exists
- the page waits for practical readiness using `Add to cart`, `Buy It Now`, or title visibility instead of relying only on network idle

### 7. Cart navigation implementation

`pages/cart_page.py` no longer depends on the legacy direct cart URL flow.

Current cart path:
- dismiss blocking add-to-cart overlays first
- click the header cart badge
- accept either direct navigation to `cart.ebay.com` or the mini-cart flyout path
- click `View cart` when the flyout is shown
- wait for the actual cart URL and then parse subtotal

Subtotal parsing strategy:
- try summary locators first
- fall back to itemized prices when needed
- validate subtotal against the expected budget threshold

### 8. Reporting implementation

Reporting is per pytest invocation, not per individual parametrized case.

Current artifact layout:

```text
reports/<timestamp>_<label>_<id>/
  |-- allure-results/
  |-- screenshots/
  `-- traces/
```

Behavior:
- run folder label is derived from the pytest target, or overridden by `--run-label`
- screenshots and traces go into the same run-scoped folder
- Allure failure hook attaches screenshot and current URL on test failure
- additional flow screenshots are saved by utility/workflow code

## CAPTCHA Handling

This project runs against a live public site, so CAPTCHA cannot be fully eliminated. The framework detects challenges at every critical step (product page load, add-to-cart click, cart page, login) and responds with `pytest.skip()` plus evidence capture instead of crashing the test run.

Supporting mitigations:
- randomized inter-item delays and browser fingerprint controls reduce trigger frequency
- storage-state persistence (`--storage-state` / `--save-storage-state`) lets trusted sessions carry across runs
- shipping/locale preferences are initialized once per page via `HomePage` to stabilize pricing and reduce challenge variance

## Configuration

All runtime behavior is centralized in `config/settings.py` and can be overridden from `.env`.

### Core Runtime Variables

```env
EBAY_BASE_URL=https://www.ebay.com

HEADLESS=false
BROWSER=chromium
BROWSER_CHANNEL=chrome
SLOW_MO=0

DEFAULT_TIMEOUT=30000
LOCATOR_ATTEMPT_TIMEOUT=5000
MAX_RETRIES=3
BACKOFF_FACTOR=2.0

SCREENSHOT_ON_FAILURE=true
REPORTS_DIR=reports
LOG_LEVEL=INFO
LOG_FILE=
```

### Currency and Shipping

```env
PREFERRED_CURRENCY=ILS
STRICT_CURRENCY_VALIDATION=false
SHIPPING_COUNTRY=Israel
SHIPPING_ZIPCODE=
```

### Browser Fingerprint / Session Controls

```env
MASK_AUTOMATION=true
BROWSER_LOCALE=en-US
TIMEZONE_ID=America/New_York
ACCEPT_LANGUAGE=en-US,en;q=0.9
USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36

STORAGE_STATE_PATH=
SAVE_STORAGE_STATE_PATH=

ANTI_BOT_DELAY_MIN=1.5
ANTI_BOT_DELAY_MAX=4.0
PLAYWRIGHT_TRACE=false
```

### Run Label / Reporting

```env
RUN_LABEL=
RUN_ID=
```

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install --with-deps
```

## Running Tests

### Main E2E suite

```bash
pytest tests/test_e2e_full_flow.py
```

### Headed run

```bash
set HEADLESS=false
pytest tests/test_e2e_full_flow.py
```

### Single browser profile

```bash
pytest tests/test_e2e_full_flow.py --browser-profile=chrome
pytest tests/test_e2e_full_flow.py --browser-profile=msedge
pytest tests/test_e2e_full_flow.py --browser-profile=firefox
```

### Trace-enabled debug run

```bash
pytest tests/test_e2e_full_flow.py --pw-trace
```

### Custom report label

```bash
pytest tests/test_e2e_full_flow.py --run-label=submission_smoke
```

### Load a trusted storage state

```bash
pytest tests/test_e2e_full_flow.py --storage-state=.auth/ebay_state.json
```

### Save storage state after the run

```bash
pytest tests/test_e2e_full_flow.py --save-storage-state=.auth/ebay_state.json
```

### Retry example

```bash
pytest tests/test_e2e_full_flow.py --reruns=1 --reruns-delay=3
```

## Test Data

Primary E2E scenarios come from `data/search_data.json`.

Current scenarios:

| Scenario | Keyword | Max Price | Limit |
|---|---|---:|---:|
| `shoes_under_500` | `shoes` | 500 | 2 |
| `wireless_headphones_under_100` | `wireless headphones` | 100 | 5 |
| `usb_cable_under_30` | `usb-c cable` | 30 | 3 |

Additional unit-support and edge-case data lives in `data/test_data.json`.

## Unit Test Coverage

The repository is not limited to the single submission E2E scenario. It also includes focused tests that validate supporting framework functionality.

Current focused coverage includes:
- login workflow behavior and CAPTCHA interruption handling in `tests/test_login_unit.py` — uses `unittest.mock.MagicMock` and `monkeypatch` to mock the Playwright page and `LoginPage`, so login tests run entirely in Python without launching a browser
- product-page variant selection and add-to-cart modal logic in `tests/test_product_page.py`
- search-related behavior and supporting assertions in `tests/test_search.py`

This means the project validates both:
- end-to-end business flow through `tests/test_e2e_full_flow.py`
- lower-level page and workflow behavior through smaller targeted tests

## Reporting

Pytest prints the active run directory at session start.

Artifacts are written to:

```text
reports/<timestamp>_<label>_<id>/allure-results/
reports/<timestamp>_<label>_<id>/screenshots/
reports/<timestamp>_<label>_<id>/traces/
```

Important notes:
- one run folder is created per pytest invocation
- raw `allure-results/` files use UUID naming and are not intended for manual inspection
- `screenshots/` is timestamp-prefixed and much easier to inspect by hand
- the run label is auto-derived from the selected target, for example `test_e2e_full_flow`
- use `--run-label` or `RUN_LABEL` to force a readable label for smoke, CI, or submission runs

Generate a local report with:

```bash
allure serve reports/<run_id>/allure-results
```

## CI / GitHub Actions

The pipeline is defined in `.github/workflows/e2e.yml`.

Current behavior:
- run unit tests first
- run the E2E suite across `chrome`, `msedge`, and `firefox`
- upload Allure raw results per job
- upload screenshots on failure
- upload traces when present
- merge Allure results
- publish the generated report to GitHub Pages from `main`

## Practical Notes

- This is a live-site framework, so eBay can still challenge sessions with CAPTCHA.
- The framework already includes mitigation and evidence capture, but it cannot guarantee a challenge-free run.
- For the cleanest submission runs, use a stable session via storage state, keep region settings coherent, and avoid changing browser fingerprint controls between runs.
