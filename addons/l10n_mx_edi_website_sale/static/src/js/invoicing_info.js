import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";


export class WebsiteSaleMXInvoicingInfoButton extends Interaction {
    static selector = "#form_l10n_mx_invoicing_info";

    dynamicSelectors = {
        ...this.dynamicSelectors,
        _submitbuttons: () => document.querySelectorAll('[name="website_sale_main_button"]'),
    };
    dynamicContent = {
        _submitbuttons: {"t-on-click.prevent": this.locked(() => this.el.submit(), true)},
    };
}

registry
    .category("public.interactions")
    .add("l10n_mx_edi_website_sale.invoicing_info", WebsiteSaleMXInvoicingInfoButton);
