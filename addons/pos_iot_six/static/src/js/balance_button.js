/** @odoo-module **/
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";

patch(Navbar.prototype, {
    setup() {
        super.setup();
        this.sendBalance = this.sendBalance.bind(this);
    },

    sendBalance() {
        for (const pm of this.pos.config.payment_method_ids) {
            if (pm.use_payment_terminal === "six_iot") {
                pm.payment_terminal.sendBalance();
            }
        }
    },
});
