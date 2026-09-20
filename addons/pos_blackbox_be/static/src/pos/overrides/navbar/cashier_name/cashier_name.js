import { CashierName } from "@point_of_sale/app/components/navbar/cashier_name/cashier_name";
import { patch } from "@web/core/utils/patch";

patch(CashierName.prototype, {
    async selectCashier(pin = false, login = false, list = false) {
        const selectedCashier = await super.selectCashier(...arguments);
        if (selectedCashier && this.pos.useBlackBoxBe() && !this.pos.userSessionStatus) {
            await this.pos.clock(true);
        }
        return selectedCashier;
    },
});
