import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";
import AppointmentCrmSteps from "@appointment_crm/../tests/tours/appointment_crm_steps";

const appointmentCrmSteps = new AppointmentCrmSteps();

registry.category("web_tour.tours").add("appointment_crm_forced_staff_user_tour", {
    url: "/appointment",
    steps: () => [
    ...appointmentCrmSteps._goToAppointment("Resource Time Appointment"),
    {
        content: "Select a time slot.",
        trigger: ".o_slots_list .o_slot_hours:first-child",
        run: "click",
        expectUnloadPage: true,
    },
    {
        content: "Fill the full name field in the appointment form.",
        trigger: "input[name='name']",
        run: function () {
            if (!this.anchor.value){
                this.anchor.value = "Customer Name";
            }
        },
    },
    {
        content: "Fill the email field in the appointment form.",
        trigger: "input[name='email']",
        run: function () {
            if (!this.anchor.value){
                this.anchor.value = "customer@odoo.com";
            }
        },
    },
    {
        content: "Fill the phone number field in the appointment form.",
        trigger: "input[type='phone']",
        run: function () {
            if (!this.anchor.value){
                this.anchor.value = "+1 555-555-5555";
            }
        },
    },
    {
        content: "Submit the appointment form.",
        trigger: ".o_appointment_form_confirm_btn",
        run: "click",
        expectUnloadPage: true,
    },
    stepUtils.goToUrl("/appointment"),
    ...appointmentCrmSteps._goToAppointment("Create"),
    {
        content: "Verify presence the forced staff user alert with the correct salesperson.",
        trigger: ".o_appointment_forced_staff_user_assigned:contains('Laetitia Sales Leads')",
    },
    {
        content: "Select a time slot.",
        trigger: ".o_slots_list .o_slot_hours:first-child",
        run: "click",
        expectUnloadPage: true,
    },
    {
        content: "Submit the appointment form.",
        trigger: ".o_appointment_form_confirm_btn",
        run: "click",
        expectUnloadPage: true,
    },
]});
