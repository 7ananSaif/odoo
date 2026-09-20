import { registry } from "@web/core/registry";
import * as tourUtils from "@website_sale/js/tours/tour_utils";

registry.category("web_tour.tours").add('shop_checkout_address', {
    url: '/shop',
    steps: () => [
        ...tourUtils.searchProduct("Storage Box", { select: true }),
        {
            id: 'add_cart_step',
            content: "click on add to cart",
            trigger: '#product_detail form #add_to_cart',
            run: "click",
        },
            tourUtils.goToCart(),
        {
            content: "go to address form",
            trigger: 'a[href="/shop/checkout?try_skip_step=true"]',
            run: "click",
            expectUnloadPage: true,
        },
        // check if the fields Codice Fiscale and PA index are present
        {
            content: "check if the fields Codice Destinatario is present",
            trigger: 'input[name="l10n_it_pa_index"]',
            run: "edit 1234567890123456789012345",
        },
        {
            content: "check if the fields Codice Fiscale is present",
            trigger: 'input[name="l10n_it_codice_fiscale"]',
            run: "edit 12345678901",
        },
    ]
});
