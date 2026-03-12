"""Full E2E flow: search, add to cart, and verify cart total stays in budget."""

import allure
import pytest

from functions.cart_actions import add_items_to_cart, assert_cart_total_not_exceeds
from functions.search import search_items_by_name_under_price
from tests.conftest import load_search_data


search_scenarios = load_search_data()


@allure.suite("E2E")
@allure.story("Search, Add to Cart, Verify Budget")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("Full end-to-end flow: search for items under a budget, add them to cart, and verify cart total.")
@pytest.mark.e2e
@pytest.mark.smoke
@pytest.mark.parametrize(
    "data",
    search_scenarios,
    ids=[scenario["test_name"] for scenario in search_scenarios],
)
def test_ebay_e2e_search_add_verify(page, data):
    max_price = data["max_price"]
    urls = search_items_by_name_under_price(
        page,
        query=data["keyword"],
        max_price=max_price,
        limit=data["limit"],
    )
    assert len(urls) > 0, f"No items found for '{data['keyword']}' under {max_price}"

    added_items = add_items_to_cart(page, urls)
    assert added_items, f"No items were added to the cart for '{data['keyword']}'"
    items_added = len(added_items)
    assert_cart_total_not_exceeds(
        page,
        budget_per_item=max_price,
        items_count=items_added,
    )
