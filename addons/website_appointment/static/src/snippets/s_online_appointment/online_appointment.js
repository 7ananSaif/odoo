import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { redirect } from "@web/core/utils/urls";

export class OnlineAppointmentCta extends Interaction {
    static selector = ".s_online_appointment";
    dynamicContent = {
        _root: {
            "t-on-click": this.onCtaClick,
        },
    }

    onCtaClick(ev) {
        const url = new URL("/appointment", window.location.origin);
        const selectedAppointments = ev.target.closest(".s_online_appointment").dataset.appointmentTypes;
        const appointmentsTypeIds = selectedAppointments ? JSON.parse(selectedAppointments) : [];
        const nbSelectedAppointments = appointmentsTypeIds.length;
        if (nbSelectedAppointments === 1) {
            url.pathname += `/${encodeURIComponent(appointmentsTypeIds[0])}`;
            const selectedUsers = ev.target.closest(".s_online_appointment").dataset.staffUsers;
            if (JSON.parse(selectedUsers).length) {
                url.searchParams.set("filter_staff_user_ids", selectedUsers);
            }
        } else if (nbSelectedAppointments > 1) {
            url.searchParams.set("filter_appointment_type_ids", selectedAppointments);
        }
        redirect(url);
    }
}

registry
    .category("public.interactions")
    .add("website_appointment.online_appointments", OnlineAppointmentCta);

