import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";

patch(ClosePosPopup.prototype, {
    async closeSession() {
        const { iotId, identifier } = this.pos.hardwareProxy.deviceControllers.display || {};
        if (this.pos.config.iface_display_id && iotId && identifier) {
            this.pos.iotHttp.action(iotId, identifier, { action: "close" });
        }
        await super.closeSession(...arguments);
    },
});
