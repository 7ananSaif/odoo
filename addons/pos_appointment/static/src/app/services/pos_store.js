import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        const { current, params } = this.router.state;
        if (current === "ActionScreen" && params?.actionName === "manage-booking") {
            this.manageBookings();
        }
    },
    async manageBookings() {
        this.orderToTransferUuid = null;
        this.navigate("ActionScreen", { actionName: "manage-booking" });
        await this.action.doAction(
            await this.data.call("calendar.event", "action_open_booking_gantt_view", [false], {
                context: { appointment_type_id: this.config.raw.appointment_type_id },
            })
        );
    },
    async editBooking(appointment) {
        const action = await this.data.call("calendar.event", "action_open_booking_form_view", [
            appointment.id,
        ]);
        return this.action.doAction(action);
    },
});
