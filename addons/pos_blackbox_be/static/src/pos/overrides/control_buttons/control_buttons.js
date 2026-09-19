import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

patch(ControlButtons.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
    },
    clickRefund() {
        if (this.pos.useBlackBoxBe() && !this.pos.userSessionStatus) {
            this.dialog.add(AlertDialog, {
                title: this._t("POS error"),
                body: this._t(
                    "The government's Fiscal Data Module requires every user to Clock In before " +
                        "sending an order.\n" +
                        "You can Clock In from the top-right menu (\u2261)."
                ),
            });
            return;
        }
        super.clickRefund();
    },
    async clickPrintBill() {
        const order = this.pos.getOrder();
        if (this.pos.useBlackBoxBe() && order.getOrderlines().length > 0) {
            this.pos.addPendingOrder([order.id]);
            await this.pos.syncAllOrders({ throw: true });
        }
        await super.clickPrintBill();
    },
    async applyDiscount(pc) {
        if (this.pos.useBlackBoxBe()) {
            try {
                this.pos.waitBeforePayment = true;
                const order = this.pos.getOrder();
                const lines = order.getOrderlines();
                this.pos.multiple_discount = true;

                await this.pos.pushCorrection(order); //push the correction order

                for (const line of lines) {
                    await this.pos.setDiscountFromUI(line, pc);
                }
                this.pos.addPendingOrder([order.id]);
                await this.pos.syncAllOrders({ throw: true });
            } finally {
                this.pos.multiple_discount = false;
                this.pos.waitBeforePayment = false;
            }
        } else {
            await super.applyDiscount(...arguments);
        }
    },
});
