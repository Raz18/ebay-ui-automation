# eBay E2E Automation — Task Tracker

## Phase 1: Foundation ✅
- [x] `requirements.txt`
- [x] `pytest.ini`
- [x] `config/settings.py`
- [x] `config/browser_profiles.py`
- [x] `utils/logger.py`
- [x] `utils/data_loader.py`
- [x] `utils/price_parser.py`
- [x] `utils/screenshot_helper.py`
- [x] Verify: imports resolve, logger outputs to console

## Phase 2: Resilience Core ✅
- [x] `utils/locator_engine.py` — full smart locator fallback
- [x] `utils/retry_handler.py` — retry + backoff + recovery
- [x] Unit tests for LocatorEngine and RetryHandler (mock-based) — 17/17 pass

## Phase 3: Base Page + Locators ✅
- [x] `pages/base_page.py` — wraps LocatorEngine + RetryHandler, @allure.step
- [x] Locators defined with diverse strategies (css, xpath, text, label, placeholder, test_id)
- [x] Verify: 51 total locators validated (min 2 mixed strategies each)

## Phase 4: Page Objects + Core Functions ✅
- [x] Locators unified into page classes (removed separate `locators/*.py` files)
- [x] `pages/home_page.py` — search + cookie consent (7 locators)
- [x] `pages/login_page.py` — multi-step sign-in + CAPTCHA detection (8 locators)
- [x] `pages/search_results_page.py` — price filter + item extraction + pagination (12 locators)
- [x] `pages/product_page.py` — variant selection + add to cart + post-cart modal (12 locators)
- [x] `pages/cart_page.py` — total parsing + itemized prices (10 locators)
- [x] `functions/login.py` — login orchestration
- [x] `functions/search.py` — search_items_by_name_under_price (full pagination logic)
- [x] `functions/cart_actions.py` — add_items_to_cart + assert_cart_total_not_exceeds
- [x] Verify: 51 locators across 5 page classes, all imports OK, 17/17 tests pass

## Phase 5: Tests + Data ✅
- [x] `data/search_data.json` — 3 scenarios (shoes, headphones, USB cables)
- [x] `data/credentials.yaml` — placeholder with env var override
- [x] `conftest.py` (root) — browser lifecycle, Allure hooks, screenshot on failure
- [x] `tests/conftest.py` — page object fixtures, data loading helpers
- [x] `tests/test_login.py` — multi-step login with CAPTCHA skip
- [x] `tests/test_search.py` — parametrized search + pagination + no-results edge case
- [x] `tests/test_add_to_cart.py` — add items + BIN-only graceful skip
- [x] `tests/test_e2e_full_flow.py` — THE MAIN SCENARIO (parametrized: search → add → assert)
- [x] `tests/test_cart_assertion.py` — positive + negative budget assertion
- [x] Verify: 30 tests collected, 17 unit tests pass, all imports OK

## Phase 6: Parallel + CI/CD + Reports ✅
- [x] Update `conftest.py` for browser matrix parametrization (`--browser-profile` CLI)
- [x] `ci/github-actions.yml` — unit + E2E matrix (chrome/msedge/firefox) + Allure report
- [x] Allure report generation + screenshot attachment
- [x] Verify: 48 tests collected, 35 unit tests pass, all imports OK

## Phase 7: Polish + README ✅
- [x] `README.md` — full setup, run, and architecture docs
- [x] Performance: replaced networkidle with load, cached Settings in retry_handler
- [x] Fixed `data-test-id` attribute (Playwright `set_test_id_attribute`)
- [x] Verified: 48 tests collected, 35 unit tests pass (0 failures)
