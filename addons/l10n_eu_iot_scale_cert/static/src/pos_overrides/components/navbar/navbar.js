import { patch } from "@web/core/utils/patch";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { ScaleCertificationStatus } from "@l10n_eu_iot_scale_cert/app/scale_certification_status/scale_certification_status";

patch(Navbar, {
    components: { ...Navbar.components, ScaleCertificationStatus },
});

patch(Navbar.prototype, {
    openCustomerDisplay() {
        const { iotId, identifier } = this.pos.hardwareProxy.deviceControllers.display || {};
        if (this.pos.config.iface_display_id && iotId && identifier) {
            this.pos.iotHttp.action(iotId, identifier, {
                action: "open",
                access_token: this.pos.config.access_token,
                pos_id: this.pos.config.id,
            });
        } else {
            super.openCustomerDisplay();
        }
    },
});
