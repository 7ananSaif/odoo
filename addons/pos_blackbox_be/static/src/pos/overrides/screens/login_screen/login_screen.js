/** @odoo-module **/

import { LoginScreen } from "@point_of_sale/app/screens/login_screen/login_screen";
import { patch } from "@web/core/utils/patch";

patch(LoginScreen.prototype, {
    async selectCashier(pin = false, login = false, list = false) {
        const result = await super.selectCashier(...arguments);
        if (
            result &&
            !this.pos.shouldShowOpeningControl() &&
            this.pos.useBlackBoxBe() &&
            !this.pos.userSessionStatus &&
            this.pos.router.state.current != "LoginScreen"
        ) {
            await this.pos.clock(true);
        }
        return result;
    },
});
