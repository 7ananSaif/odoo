/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";

patch(TicketScreen.prototype, {
    //@override
    async addAdditionalRefundInfo(order, destinationOrder) {
        if (this.pos.company.country_id?.code === "MX" && order.isToInvoice()) {
            destinationOrder.l10n_mx_edi_usage = "G02";
            destinationOrder.l10n_mx_edi_cfdi_to_public = order.l10n_mx_edi_cfdi_to_public;
        }
    },
});
