import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { AppointmentTypeListController} from "@appointment/views/list/list_controller";
import { AppointmentBookingListRenderer, AppointmentTypeListRenderer} from "@appointment/views/list/list_renderer";

export const AppointmentBookingListView = {
    ...listView,
    Renderer: AppointmentBookingListRenderer,
};

registry.category("views").add("appointment_booking_list", AppointmentBookingListView);

export const AppointmentTypeListView = {
    ...listView,
    Controller: AppointmentTypeListController,
    Renderer: AppointmentTypeListRenderer,
};

registry.category("views").add("appointment_type_list", AppointmentTypeListView);
