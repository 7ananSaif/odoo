import { OpeningControlPopup } from "@point_of_sale/app/components/popups/opening_control_popup/opening_control_popup";
import { patch } from "@web/core/utils/patch";

patch(OpeningControlPopup.prototype, {
    async confirm() {
        const { iotId, identifier } = this.pos.hardwareProxy.deviceControllers.display || {};
        if (this.pos.config.iface_display_id && iotId && identifier) {
            this.pos.iotHttp.action(iotId, identifier, {
                action: "open",
                access_token: this.pos.config.access_token,
                pos_id: this.pos.config.id,
            });
        }
        await super.confirm(...arguments);
    },
});
