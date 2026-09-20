import { registry } from "@web/core/registry";
import * as tourUtils from "@website_sale/js/tours/tour_utils";

registry.category("web_tour.tours").add("shop_buy_rental_product_wishlist", {
    url: "/shop?search=Computer",
    steps: () => [
        {
            content: "Hover on image and click on add to wishlist",
            trigger: "img[alt=Computer]",
            run: "hover && click .o_add_wishlist",
        },
        {
            trigger: 'a[href="/shop/wishlist"] .badge.bg-primary:contains(1)',
        },
        {
            content: "go to wishlist",
            trigger: 'a[href="/shop/wishlist"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "click on add to cart",
            trigger: ".o_wish_add",
            run: "click",
            expectUnloadPage: true,
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
