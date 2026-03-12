"""Search orchestration: search for items under a max price with pagination."""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

import allure

from config.settings import Settings
from pages.home_page import HomePage
from pages.search_results_page import SearchResultsPage
from utils.logger import get_logger

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = get_logger(__name__)


# Track which pages have had home preferences initialized.
# WeakSet drops references automatically when the Page is garbage-collected,
# avoiding false hits from id() reuse.
_initialized_pages: weakref.WeakSet = weakref.WeakSet()


def _ensure_home_preferences(page: Page) -> None:
    """Open eBay home once per test page to apply cookie and shipping preferences."""
    if page in _initialized_pages:
        return

    HomePage(page).navigate_to_home()
    _initialized_pages.add(page)


def _open_search_results(page: Page, query: str) -> SearchResultsPage:
    _ensure_home_preferences(page)

    settings = Settings.from_env()
    base = settings.BASE_URL.rstrip("/")
    search_url = f"{base}/sch/i.html?_nkw={quote_plus(query)}"
    page.goto(search_url, wait_until="domcontentloaded")
    results_page = SearchResultsPage(page)
    results_page.wait_for_results()
    return results_page


def _collect_search_urls(page: Page, query: str, max_price: float, limit: int) -> list[str]:
    results_page = _open_search_results(page, query)
    results_page.apply_price_filter(max_price)
    if not results_page.has_results():
        logger.warning("No results found for '%s'", query)
        return []

    collected_urls: list[str] = []
    seen_urls: set[str] = set()
    visited_results_urls: set[str] = {results_page.current_url}
    while len(collected_urls) < limit:
        remaining = limit - len(collected_urls)
        candidate_urls = results_page.collect_items_under_price(max_price, remaining)

        for url in candidate_urls:
            if url in seen_urls:
                continue

            seen_urls.add(url)
            collected_urls.append(url)
            if len(collected_urls) >= limit:
                break

        if len(collected_urls) >= limit or not results_page.has_next_page():
            break

        previous_results_url = results_page.current_url
        results_page.go_to_next_page()
        if results_page.current_url == previous_results_url:
            logger.warning("Pagination did not advance beyond %s", previous_results_url)
            break

        if results_page.current_url in visited_results_urls:
            logger.warning("Pagination loop detected on %s", results_page.current_url)
            break

        visited_results_urls.add(results_page.current_url)

    return collected_urls[:limit]


@allure.step("Search for '{query}' under {max_price} (limit={limit})")
def search_items_by_name_under_price(
    page: Page,
    query: str,
    max_price: float,
    limit: int = 5,
) -> list[str]:
    """Return up to `limit` product URLs whose visible result-card price is <= `max_price`."""
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        urls = _collect_search_urls(page, query, max_price, limit)
        if urls:
            return urls

        logger.warning(
            "Search attempt %d/%d returned no URLs for '%s' under %s",
            attempt,
            max_attempts,
            query,
            max_price,
        )

    return []
