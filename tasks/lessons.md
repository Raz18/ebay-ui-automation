# Lessons Learned

> Updated after every correction. Reviewed at session start.

## Patterns & Rules

### 1. Lean on Playwright built-ins — don't over-engineer
- Playwright's `page.locator()` auto-detects CSS vs XPath — no need for separate dispatch per selector type.
- `page.get_by_role()`, `page.get_by_text()`, `page.get_by_test_id()`, `page.get_by_placeholder()`, `page.get_by_label()` cover semantic lookups natively — don't wrap them in custom abstractions.
- `locator.first.wait_for(state="visible")` handles single-element waiting. Don't build custom polling loops.
- `locator.count()` is the idiomatic way to check multi-element presence — no need for try/catch around `.all()`.
- `time.sleep()` is acceptable ONLY inside `retry_handler.py` backoff (sync Playwright is blocking). Everywhere else, use Playwright waits.
- For test-level retries, use `pytest-rerunfailures --reruns` — don't build custom test retry logic.

### 2. LocatorEngine vs RetryHandler — clear separation
- **LocatorEngine**: tries *different locators* for the same element. Number of attempts = number of locator strategies defined. No backoff.
- **RetryHandler**: retries the *same action* (click, fill, navigate) on transient failures. Uses exponential backoff. Config from `settings.py`.
- Never mix these: LocatorEngine doesn't retry a failed locator, RetryHandler doesn't switch locators.

### 3. Keep abstractions thin
- `LocatorEngine._resolve()` uses Python `match` statement to map strategy → Playwright method. One line per strategy. No class hierarchy needed.
- `RetryHandler.with_retry()` is a simple function, not a class with lifecycle. Decorator `@retry` is a thin wrapper over it.
- Don't create abstract base classes unless there are 3+ implementations.
