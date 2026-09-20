import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export class AppointmentTypeSelect extends Interaction {
    static selector = ".o_appointment_choice";
    dynamicContent = {
        ".o_appointment_select_button": {
            "t-on-click.prevent.stop": this.onAppointmentTypeSelected,
        },
        "select[id='appointment_type_id']": {
            "t-on-change": this.debounced(this.onAppointmentTypeChange, 250),
        },
        ".o_appointment_not_found > div": {
            "t-att-class": () => ({
                "d-none": false,
            }),
        },
    };

    start() {
        // Load an image when no appointment types are found
        // TODO: maybe define a "replace" position in renderAt
        const el = this.el.querySelector(".o_appointment_svg i");
        if (el) {
            this.renderAt("Appointment.appointment_svg", {}, el, "afterend");
            el.remove();
        }
    }

    /**
     * On appointment type change: adapt appointment intro text and available
     * users. (if option enabled)
     *
     * @param {Event} ev
     */
    async onAppointmentTypeChange(ev) {
        const appointmentTypeID = ev.target.value;
        const filterAppointmentTypeIds = this.el.querySelector(
            "input[name='filter_appointment_type_ids']"
        ).value;
        const filterUserIds = this.el.querySelector("input[name='filter_staff_user_ids']").value;
        const filterResourceIds = this.el.querySelector("input[name='filter_resource_ids']").value;
        const inviteToken = this.el.querySelector("input[name='invite_token']").value;

        const messageIntro = await this.waitFor(
            rpc(`/appointment/${appointmentTypeID}/get_message_intro`, {
                invite_token: inviteToken,
                filter_appointment_type_ids: filterAppointmentTypeIds,
                filter_staff_user_ids: filterUserIds,
                filter_resource_ids: filterResourceIds,
            })
        );
        this.protectSyncAfterAsync(() => {
            const parsedElements = new DOMParser().parseFromString(messageIntro, "text/html").body
                .childNodes;
            this.el.querySelector(".o_appointment_intro")?.replaceChildren(...parsedElements);
        })();
    }

    /**
     * On appointment type selected: redirect to the selected appointment type.
     *
     * @param {Event} ev
     */
    onAppointmentTypeSelected(ev) {
        const optionSelected = this.el.querySelector("select").selectedOptions[0];
        window.location = optionSelected.dataset.appointmentUrl;
    }
}

registry
    .category("public.interactions")
    .add("appointment.appointment_type_select", AppointmentTypeSelect);
