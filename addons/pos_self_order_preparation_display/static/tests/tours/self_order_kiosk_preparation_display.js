import { registry } from "@web/core/registry";
import * as Utils from "@pos_self_order/../tests/tours/utils/common";
import * as ProductPage from "@pos_self_order/../tests/tours/utils/product_page_util";
import * as LandingPage from "@pos_self_order/../tests/tours/utils/landing_page_util";
import * as Numpad from "@point_of_sale/../tests/generic_helpers/numpad_util";
import * as CartPage from "@pos_self_order/../tests/tours/utils/cart_page_util";

registry.category("web_tour.tours").add("self_kiosk_order_preparation_display", {
    steps: () => [
        Utils.clickBtn("Order Now"),
        LandingPage.selectLocation("Test-In"),
        ProductPage.clickProduct("Coca-Cola"),
        Utils.clickBtn("Checkout"),
        Utils.clickBtn("Order"),
        Numpad.click("3"),
        Utils.clickBtn("Order"),
        Utils.clickBtn("Close"),
    ],
});

registry.category("web_tour.tours").add("test_ensure_mobile_order_preparation_display", {
    steps: () =>
        [
            Utils.clickBtn("Order Now"),
            LandingPage.selectLocation("Test-In"),
            ProductPage.clickProduct("Coca-Cola"),
            Utils.clickBtn("Checkout"),
            Utils.clickBtn("Order"),
            {
                trigger: ".confirmation-page:contains('Pay $ 2.53 at the counter')",
            },
            Utils.clickBtn("Ok"),
            Utils.clickBtn("My Order"),
            CartPage.isShown(),
            Utils.clickBtn("Cancel"),
            Utils.clickBtn("Cancel Order"),
            CartPage.clickBack(),
            Utils.checkBtn("My Order"),
        ].flat(),
});
