import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";
import { findInvalidEmailFromText } from  "../js/utils.js"
import { _t } from "@web/core/l10n/translation";
import { addLoadingEffect } from "@web/core/utils/ui";

export class AppointmentForm extends Interaction {
    static selector = ".o_appointment_attendee_form";
    dynamicContent = {
        "div.o_appointment_add_guests button.o_appointment_input_guest_add": {
            "t-on-click.noUpdate": this.onAddGuest,
        },
        "#o_appointment_input_guest_emails": {
            "t-att-class": () => ({
                "d-none": !this.showAddGuest,
            }),
        },
        "button.o_appointment_input_guest_add": {
            "t-att-class": () => ({
                "d-none": this.showAddGuest,
            }),
        },
        "button.o_appointment_input_guest_cancel": {
            "t-att-class": () => ({
                "d-none": !this.showAddGuest,
            }),
        },
        "div.o_appointment_add_guests button.o_appointment_input_guest_cancel": {
            "t-on-click": this.onHideGuest,
        },
        ".o_appointment_form_confirm_btn": {
            "t-on-click": this.onConfirmAppointment,
        },
        ".o_appointment_validation_error": {
            "t-att-class": () => ({
                "d-none": this.errorMessage === "",
            }),
        },
        ".o_appointment_error_text": {
            "t-out": () => this.errorMessage,
        },
    }

    setup() {
        this.showAddGuest = false;
        this.errorMessage = "";
    }

    start() {
        this.hasFormDefaultValues = this.getAttendeeFormData().some(([_, value]) => value !== "");
        this.mainPhoneQuestion = this.el.querySelector('input[data-is-main-phone-question="True"]');
        if (!this.hasFormDefaultValues && localStorage.getItem("appointment.form.values")) {
            const attendeeData = JSON.parse(localStorage.getItem("appointment.form.values"));
            const formEl = this.el.querySelector("form.appointment_submit_form");
            for (const [name, value] of Object.entries(attendeeData)) {
                if (name === 'phone' && !this.mainPhoneQuestion) {
                    continue;
                }
                const inputEl = name === 'phone' ?
                    this.mainPhoneQuestion :
                    formEl.querySelector(`input[name="${name}"]`);
                if (inputEl) {
                    inputEl.value = value;
                }
            }
        }
    }

    getAttendeeFormData() {
        const formData = new FormData(this.el.querySelector("form.appointment_submit_form"));
        const formKeys = this.mainPhoneQuestion ?
            [this.mainPhoneQuestion.name, "name", "email"] :
            ["name", "email"];
        return Array.from(formData).filter(([key]) => formKeys.includes(key));
    }

    /**
     * This function will show the guest email textarea where user can enter the
     * emails of the guests if allow_guests option is enabled.
     */
    onAddGuest() {
        this.showAddGuest = true;
        this.updateContent();
        const textAreaEl = this.el.querySelector("#o_appointment_input_guest_emails");
        textAreaEl.focus();
    }

    onConfirmAppointment (event) {
        this.validateCheckboxes();
        const textAreaEl = this.el.querySelector("#o_appointment_input_guest_emails");
        const appointmentFormEl = document.querySelector(".appointment_submit_form");
        if (textAreaEl && textAreaEl.value.trim() !== "") {
            let emailInfo = findInvalidEmailFromText(textAreaEl.value);
            if (emailInfo.invalidEmails.length || emailInfo.emailList.length > 10) {
                this.errorMessage = emailInfo.invalidEmails.length > 0 ? _t("Invalid Email") : _t("You cannot invite more than 10 people");
                return;
            } else {
                this.errorMessage = "";
            }
        }
        if (appointmentFormEl.reportValidity()) {
            if (!this.hasFormDefaultValues) {
                const attendeeData = this.getAttendeeFormData();
                if (attendeeData.length) {
                    const attendeeDataObject = Object.fromEntries(attendeeData);
                    if (this.mainPhoneQuestion){
                        attendeeDataObject['phone'] = attendeeDataObject[this.mainPhoneQuestion.name];
                        delete attendeeDataObject[this.mainPhoneQuestion.name];
                    }
                    localStorage.setItem("appointment.form.values", JSON.stringify(attendeeDataObject));
                }
            }
            appointmentFormEl.submit();
            addLoadingEffect(event.target);
        }
    }

    /**
     * This function will hide the guest email textarea if allow_guests option is enabled.
     */
    onHideGuest() {
        this.errorMessage = "";
        this.showAddGuest = false;
        const textAreaEl = this.el.querySelector("#o_appointment_input_guest_emails");
        textAreaEl.value = "";
    }

    validateCheckboxes() {
        this.el.querySelectorAll(".checkbox-group.required").forEach((groupEl) => {
            const checkboxEls = groupEl.querySelectorAll(".checkbox input");
            checkboxEls.forEach(
                (checkboxEl) =>
                    (checkboxEl.required = ![...checkboxEls].some(
                        (checkboxEl) => checkboxEl.checked
                    ))
            );
        });
    }
}


registry
    .category("public.interactions")
    .add("appointment.appointment_form", AppointmentForm);

