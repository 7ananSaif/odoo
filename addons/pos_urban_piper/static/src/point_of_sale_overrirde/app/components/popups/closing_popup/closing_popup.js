import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";

patch(ClosePosPopup.prototype, {
    /**
     * @override
     */
    async confirm() {
        await this.pos.updateStoreStatus();
        localStorage.removeItem("toggle_state_" + this.pos.config.id);
        return super.confirm();
    },
});
