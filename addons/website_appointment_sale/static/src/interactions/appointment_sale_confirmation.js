import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

import { user } from "@web/core/user";

export class AppointmentSaleConfirmation extends Interaction {
    static selector = ".o_wappointment_sale_confirmation_card";

    /**
     * Store in local storage the appointment booked for the appointment type.
     * This value is used later to display information on the upcoming appointment
     * if an appointment is already taken. If the user is logged don't store anything
     * as everything is computed by the /appointment/get_upcoming_appointments route.
     */
    setup() {
        if (user.userId) {
            return;
        }
        const eventAccessToken = this.el.dataset.eventAccessToken;
        const allAppointmentsToken = JSON.parse(localStorage.getItem("appointment.upcoming_events_access_token")) || [];
        if (eventAccessToken && !allAppointmentsToken.includes(eventAccessToken)) {
            allAppointmentsToken.push(eventAccessToken);
            localStorage.setItem("appointment.upcoming_events_access_token", JSON.stringify(allAppointmentsToken));
        }
    }
}

registry
    .category("public.interactions")
    .add("website_appointment_sale.appointment_sale_confirmation", AppointmentSaleConfirmation);
