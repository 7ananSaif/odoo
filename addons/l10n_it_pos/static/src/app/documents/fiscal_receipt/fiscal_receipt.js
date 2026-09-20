import { Component } from "@odoo/owl";
import { Header, Body, Footer } from "@l10n_it_pos/app/documents/fiscal_document";

export class FiscalReceipt extends Component {
    static template = "l10n_it_pos.FiscalReceipt";

    static components = {
        Header,
        Body,
        Footer,
    };

    static props = {
        order: {
            type: Object,
            optional: true, // To keep backward compatibility
        },
    };
}
