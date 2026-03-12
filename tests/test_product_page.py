"""Unit tests for product-page variant handling."""

from unittest.mock import MagicMock

import allure

from pages.product_page import ProductPage


@allure.suite("Unit Tests")
@allure.story("Variant Selection")
def test_dropdown_variant_chooses_a_valid_option():
    page = MagicMock()
    product = ProductPage(page)

    select_locator = MagicMock()
    placeholder = MagicMock()
    placeholder.get_attribute.side_effect = lambda name: {"value": "-1", "disabled": None}.get(name)
    placeholder.text_content.return_value = "Select"

    first_valid = MagicMock()
    first_valid.get_attribute.side_effect = lambda name: {"value": "0", "disabled": None}.get(name)
    first_valid.text_content.return_value = "Black"

    second_valid = MagicMock()
    second_valid.get_attribute.side_effect = lambda name: {"value": "1", "disabled": None}.get(name)
    second_valid.text_content.return_value = "White"

    select_locator.locator.return_value.all.return_value = [placeholder, first_valid, second_valid]
    product._find_optional = MagicMock(return_value=select_locator)

    product._try_select_dropdown_variant(product.COLOR_DROPDOWN, "Color")

    select_locator.select_option.assert_called_once()
    chosen_value = select_locator.select_option.call_args[1]["value"]
    assert chosen_value in ("0", "1"), f"Expected a valid option, got {chosen_value}"


@allure.suite("Unit Tests")
@allure.story("Variant Selection")
def test_custom_listbox_chooses_a_valid_option():
    page = MagicMock()
    product = ProductPage(page)

    controls_locator = MagicMock()
    control = MagicMock()
    control.get_attribute.side_effect = lambda name: None if name == "disabled" else "false"

    placeholder = MagicMock()
    placeholder.get_attribute.side_effect = lambda name: None
    placeholder.text_content.return_value = "Select"

    first_valid = MagicMock()
    first_valid.get_attribute.side_effect = lambda name: "Black 1 Ft (3 Pack)" if name == "data-sku-value-name" else None
    first_valid.text_content.return_value = "Black 1 Ft (3 Pack)"

    second_valid = MagicMock()
    second_valid.get_attribute.side_effect = lambda name: "White 1 Ft (3 Pack)" if name == "data-sku-value-name" else None
    second_valid.text_content.return_value = "White 1 Ft (3 Pack)"

    control.locator.return_value.all.return_value = [placeholder, first_valid, second_valid]
    controls_locator.all.return_value = [control]
    product._find_all_optional = MagicMock(return_value=controls_locator)

    product._try_select_custom_listbox_variants()

    control.click.assert_called_once()
    # random.choice picks one of the two valid options
    total_clicks = first_valid.click.call_count + second_valid.click.call_count
    assert total_clicks == 1, "Expected exactly one valid option to be clicked"


@allure.suite("Unit Tests")
@allure.story("Variant Selection")
def test_select_first_variants_only_runs_handlers_for_present_controls():
    page = MagicMock()
    product = ProductPage(page)

    product._peek_optional = MagicMock(side_effect=lambda element, timeout_ms=500: (
        MagicMock() if element.name in {
            product.SIZE_DROPDOWN.name,
            product.VARIANT_SELECT.name,
        } else None
    ))
    product._peek_all_optional = MagicMock(side_effect=lambda element, timeout_ms=500: (
        MagicMock() if element.name == product.CUSTOM_VARIANT_LISTBOX.name else None
    ))
    product._try_select_dropdown_variant = MagicMock()
    product._try_select_custom_listbox_variants = MagicMock()
    product._try_select_button_variant = MagicMock()

    product.select_first_variants()

    product._try_select_dropdown_variant.assert_any_call(product.SIZE_DROPDOWN, "Size")
    product._try_select_dropdown_variant.assert_any_call(product.VARIANT_SELECT, "Variant")
    assert product._try_select_dropdown_variant.call_count == 2
    product._try_select_custom_listbox_variants.assert_called_once_with()
    product._try_select_button_variant.assert_not_called()


@allure.suite("Unit Tests")
@allure.story("Post Add-To-Cart Modal")
def test_handle_post_cart_modal_prefers_close_x_for_final_item():
    page = MagicMock()
    product = ProductPage(page)

    product._wait_for_cart_layer_to_appear = MagicMock(return_value=True)
    product._close_post_cart_modal_via_x = MagicMock(return_value=True)

    product.handle_post_cart_modal(prefer_close_button=True)

    product._wait_for_cart_layer_to_appear.assert_called_once_with(timeout_ms=15000)
    product._close_post_cart_modal_via_x.assert_called_once()


@allure.suite("Unit Tests")
@allure.story("Post Add-To-Cart Modal")
def test_handle_post_cart_modal_uses_close_x_when_keep_shopping_is_absent():
    page = MagicMock()
    product = ProductPage(page)

    product._wait_for_cart_layer_to_appear = MagicMock(return_value=True)
    product.is_visible = MagicMock(side_effect=lambda element, timeout_ms=None: element.name in {
        product.CLOSE_CART_LAYER.name,
    })
    product.click = MagicMock()
    product._wait_for_cart_layer_to_close = MagicMock()

    product.handle_post_cart_modal()

    product._wait_for_cart_layer_to_appear.assert_called_once_with(timeout_ms=3000)
    product.click.assert_called_once_with(product.CLOSE_CART_LAYER)
    product._wait_for_cart_layer_to_close.assert_called_once()


@allure.suite("Unit Tests")
@allure.story("Post Add-To-Cart Modal")
def test_wait_for_cart_layer_to_appear_polls_until_overlay_is_visible():
    page = MagicMock()
    product = ProductPage(page)
    attempts = {"count": 0}

    def fake_is_visible(element, timeout_ms=None):
        if element.name == product.CART_LAYER.name:
            attempts["count"] += 1
            return attempts["count"] >= 3
        return False

    product.is_visible = MagicMock(side_effect=fake_is_visible)

    assert product._wait_for_cart_layer_to_appear(timeout_ms=1000) is True
    assert attempts["count"] >= 3
