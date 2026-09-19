import { registry } from "@web/core/registry";
import * as tourUtils from "@website_sale/js/tours/tour_utils";

registry.category("web_tour.tours").add("shop_checkout_address_ec", {
    url: "/shop",
    steps: () => [
        ...tourUtils.addToCart({ productName: "Test Product", expectUnloadPage: true }),
        tourUtils.goToCart({ quantity: 1 }),
        {
            content: "Go to checkout",
            trigger: "a:contains('Checkout')",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Check that VAT field is present",
            trigger: "label:contains('Identification Type')",
        },
        {
            content: "Check that VAT field is present",
            trigger: "label:contains('Identification Number')",
        },
    ],
});

registry.category("web_tour.tours").add("tour_new_billing_ec", {
    url: "/shop",
    steps: () => [
        ...tourUtils.addToCart({ productName: "Test Product", expectUnloadPage: true }),
        tourUtils.goToCart({ quantity: 1 }),
        {
            content: "Go to checkout",
            trigger: "a:contains('Checkout')",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Fill vat",
            trigger: "#o_vat",
            run: "fill BE0477472701",
        },
        {
            content: "Save address",
            trigger: "a[name='website_sale_main_button']",
            run: "click",
            expectUnloadPage: true,
        },
        tourUtils.waitForInteractionToLoad(),
        {
            content: "Billing address is not same as delivery address",
            trigger: "#use_delivery_as_billing",
            run: "click",
        },
        {
            content: "Add new billing address",
            trigger: `#billing_address_list a[href^="/shop/address?address_type=billing"]:contains(Add address)`,
            run: "click",
            expectUnloadPage: true,
        },
        ...tourUtils.fillAdressForm(
            {
                name: "John Doe",
                phone: "123456789",
                email: "johndoe@gmail.com",
                street: "1 rue de la paix",
                city: "Paris",
                zip: "75000",
            },
            true
        ),
        {
            trigger: `[name="address_card"] address:contains(1 rue de la paix)`,
        },
    ],
});
