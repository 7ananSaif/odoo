import { patch } from "@web/core/utils/patch";
import AppointmentCrmSteps from "@appointment_crm/../tests/tours/appointment_crm_steps";

patch(AppointmentCrmSteps.prototype, {
    _goToAppointment(name) {
        return [
            {
                content: "Select an appointment.",
                trigger: `a[title='Book ${name}']`,
                run: "click",
                expectUnloadPage: true,
            },
        ];
    },
});
