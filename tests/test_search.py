"""Search tests for edge cases: pagination and no-results handling.

NOTE: Parametrized search-under-price scenarios are covered by test_e2e_full_flow.py.
This file focuses on edge cases not covered by the main E2E flow.
"""

import allure
import pytest

from functions.search import search_items_by_name_under_price
from utils.data_loader import DataLoader

edge_cases_data = DataLoader.load("data/test_data.json")["search_edge_cases"]


@allure.suite("Search")
@allure.story("Pagination")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.regression
def test_search_pagination(page):
    """Verify pagination works by searching for a common keyword with a low limit."""
    data = edge_cases_data["pagination"]
    urls = search_items_by_name_under_price(
        page,
        query=data["keyword"],
        max_price=data["max_price"],
        limit=data["limit"],
    )
    assert len(urls) > 0, f"Expected at least 1 item for '{data['keyword']}' under ILS {data['max_price']}"
    assert len(urls) <= data["limit"]


@allure.suite("Search")
@allure.story("No Results Handling")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.regression
def test_search_no_results_returns_empty(page):
    """A nonsensical query should return an empty list, not crash."""
    data = edge_cases_data["no_results"]
    urls = search_items_by_name_under_price(
        page,
        query=data["keyword"],
        max_price=data["max_price"],
        limit=data["limit"],
    )
    assert urls == []
