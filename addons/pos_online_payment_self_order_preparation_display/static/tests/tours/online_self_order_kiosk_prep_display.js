import { registry } from "@web/core/registry";
import * as Utils from "@pos_self_order/../tests/tours/utils/common";
import * as ProductPage from "@pos_self_order/../tests/tours/utils/product_page_util";

registry.category("web_tour.tours").add("test_ensure_online_self_order_prep_display", {
    steps: () => [
        Utils.clickBtn("Order Now"),
        ProductPage.clickProduct("Coca-Cola"),
        Utils.clickBtn("Checkout"),
        Utils.clickBtn("Pay"),
    ],
});

registry.category("web_tour.tours").add("test_without_online_self_order_prep_display", {
    steps: () => [
        Utils.clickBtn("Order Now"),
        ProductPage.clickProduct("Coca-Cola"),
        Utils.clickBtn("Checkout"),
        Utils.clickBtn("Order"),
    ],
});
