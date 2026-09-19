import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";

patch(Navbar.prototype, {
    get mainButton() {
        return this.pos.router.state.current === "ActionScreen" &&
            this.pos.router.state.params.actionName === "manage-booking"
            ? "booking"
            : super.mainButton;
    },
});
