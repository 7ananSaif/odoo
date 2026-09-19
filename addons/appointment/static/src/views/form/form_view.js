import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { AppointmentTypeFormController } from "./form_controller";

export const AppointmentTypeFormView = {
    ...formView,
    Controller: AppointmentTypeFormController,
};

registry.category("views").add("appointment_type_form_view", AppointmentTypeFormView);
