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
- each product opens in a temporary tab created from the search tab context
- after each item, the product tab is closed and focus is restored to the original search results tab
- a randomized anti-bot pause is inserted between items using `ANTI_BOT_DELAY_MIN` and `ANTI_BOT_DELAY_MAX`
- per-item screenshots are captured after successful add-to-cart
- failures capture dedicated evidence and continue to the next URL

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

## CAPTCHA Mitigations Already Implemented

This project runs against a live public site, so CAPTCHA cannot be fully eliminated. The framework focuses on detection, graceful handling, and session stabilization.

### Product flow mitigations

Implemented in `functions/cart_actions.py` and `pages/product_page.py`:
- detect CAPTCHA on the product page before add-to-cart
- detect CAPTCHA again immediately after clicking `Add to cart`
- skip the specific item instead of crashing the full item loop
- add randomized delay between items to reduce bursty behavior

### Cart flow mitigations

Implemented in `pages/cart_page.py` and `functions/cart_actions.py`:
- detect cart blocks by URL/title patterns such as `captcha` and `splashui`
- capture `cart_blocked` evidence before skipping
- treat CAPTCHA during subtotal read as a skip with evidence instead of a misleading assertion failure

### Login flow mitigations

Implemented in `pages/login_page.py` and `functions/login.py`:
- detect CAPTCHA iframe presence during sign-in
- raise a dedicated `CaptchaBlockedError`
- convert the error to `pytest.skip(...)` at the workflow level
- capture a screenshot when CAPTCHA is detected

### Session and browser-state mitigations

Implemented in `conftest.py` and `config/settings.py`:
- support loading a trusted Playwright storage state with `STORAGE_STATE_PATH` or `--storage-state`
- support saving storage state at teardown with `SAVE_STORAGE_STATE_PATH` or `--save-storage-state`
- support browser/session fingerprint controls through locale, timezone, Accept-Language, user agent, and `MASK_AUTOMATION`
- keep trace capture opt-in so normal E2E runs stay lighter

### Shipping / location stabilization

Implemented in `pages/home_page.py`:
- auto-dismiss cookie banner
- detect the shipping preferences iframe
- choose the configured shipping country
- optionally fill zipcode
- confirm and wait for the popup to close

This reduces variation in result pricing and item availability across runs.

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
- login workflow behavior and CAPTCHA interruption handling in `tests/test_login_unit.py`
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
