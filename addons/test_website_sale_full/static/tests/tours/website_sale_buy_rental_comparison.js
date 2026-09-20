import { registry } from "@web/core/registry";
import * as tourUtils from "@website_sale/js/tours/tour_utils";

registry.category("web_tour.tours").add("shop_buy_rental_product_comparison", {
    url: "/shop?search=Computer",
    steps: () => [
        {
            content: "hover on computer and click on add to comparison",
            trigger: "img[alt=Computer]",
            run: "hover && click .o_add_compare",
        },
        ...tourUtils.searchProduct("Color T-Shirt"),
        {
            content: "add first product 'Color T-Shirt' in a comparison list",
            trigger: '.oe_product_cart:contains("Color T-Shirt")',
        },
        {
            trigger: ".o_add_compare:hidden",
            run: "click",
        },
        {
            content: "check the compare button contains two products",
            trigger: ".o_wsale_comparison_bottom_bar .badge:contains(2)",
        },
        {
            content: "click on compare button",
            trigger: 'a:contains("Compare")',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "click on add to cart",
            trigger: '.product_summary:contains("Computer") button:contains("Add to Cart")',
            run: "click",
        },
        tourUtils.goToCart({ quantity: 1 }),
        {
            content: "Verify there is a Computer",
            trigger: '#cart_products div h6:contains("Computer")',
        },
        {
            content: "Verify there are 1 quantity of Computers",
            trigger: '#cart_products div div.css_quantity input[value="1"]',
        },
        {
            trigger: "#cart_products .oe_currency_value:contains(3.50)",
        },
        {
            content: "go to checkout",
            trigger: 'a[href*="/shop/checkout"]',
            run: "click",
            expectUnloadPage: true,
        },
        tourUtils.confirmOrder(),
        {
            content: "verify checkout page",
            trigger: 'div[name="step_name"].fw-bold:contains("Payment")',
        },
    ],
});
