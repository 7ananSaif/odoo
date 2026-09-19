import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";

patch(Navbar.prototype, {
    setup() {
        super.setup(...arguments);
        this.connectionStatus();
    },
    connectionStatus() {
        this.state.iotStatus = !this.pos.ui.isSmall && `IoT Box (${this.pos.iotHttp.status})`;
        return true;
    },
});
