import { CustomerDisplayPosAdapter } from "@point_of_sale/app/customer_display/customer_display_adapter";
import { patch } from "@web/core/utils/patch";

patch(CustomerDisplayPosAdapter.prototype, {
    dispatch(pos) {
        const { iotId, identifier } = pos.hardwareProxy.deviceControllers.display || {};
        if (pos.config.iface_display_id && iotId && identifier) {
            pos.iotHttp.action(iotId, identifier, { action: "set", data: this.data });
        } else {
            super.dispatch(pos);
        }
    },
});
