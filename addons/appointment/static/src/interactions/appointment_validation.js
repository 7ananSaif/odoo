import { browser } from "@web/core/browser/browser";
import { rpc } from "@web/core/network/rpc";
import { findInvalidEmailFromText } from "../js/utils.js";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class AppointmentValidation extends Interaction {
    static selector = ".o_appointment_validation_details";
    dynamicContent = {
        ".o_appointment_copy_link": {
            "t-on-click": this.onCopyVideocallLink,
        },
        ".o_appointment_guest_addition_open": {
            "t-on-click.noUpdate": this.onGuestAdditionOpen,
            "t-att-class": () => ({
                "d-none": this.showGuestAddition,
            }),
        },
        ".o_appointment_guest_discard": {
            "t-on-click": this.onGuestDiscard,
            "t-att-class": () => ({
                "d-none": !this.showGuestAddition,
            }),
        },
        ".o_appointment_guest_add": {
            "t-on-click": this.locked(this.onGuestAdd),
            "t-att-class": () => ({
                "d-none": !this.showGuestAddition,
            }),
        },
        ".o_appointment_validation_error": {
            "t-att-class": () => ({
                "d-none": this.errorMessage.length === 0,
            }),
        },
        ".o_appointment_error_text": {
            "t-out": () => this.errorMessage,
        },
        "#o_appointment_input_guest_emails": {
            "t-att-class": () => ({
                "d-none": !this.showGuestAddition,
            }),
        },
    };

    setup() {
        this.errorMessage = "";
        this.showGuestAddition = false;
    }

    /**
     * Store in local storage the appointment booked for the appointment type.
     * This value is used later to display information on the upcoming appointment
     * if an appointment is already taken. If the user is logged don't store anything
     * as everything is computed by the /appointment/get_upcoming_appointments route.
     */
    start() {
        if (user.userId) {
            return;
        }
        const eventAccessToken = this.el.dataset.eventAccessToken;
        const eventStart =
            (this.el.dataset.eventStart && deserializeDateTime(this.el.dataset.eventStart)) ||
            false;
        const allAppointmentsToken =
            JSON.parse(localStorage.getItem("appointment.upcoming_events_access_token")) || [];
        if (
            eventAccessToken &&
            !allAppointmentsToken.includes(eventAccessToken) &&
            eventStart &&
            eventStart > luxon.DateTime.utc()
        ) {
            allAppointmentsToken.push(eventAccessToken);
            localStorage.setItem(
                "appointment.upcoming_events_access_token",
                JSON.stringify(allAppointmentsToken)
            );
        }
    }

    onCopyVideocallLink(ev) {
        const copyButtonEl = ev.target;
        const tooltip = Tooltip.getOrCreateInstance(copyButtonEl, {
            title: _t("Link Copied!"),
            trigger: "manual",
            placement: "right",
        });
        this.waitForTimeout(
            async () => await browser.navigator.clipboard.writeText(copyButtonEl.dataset.value),
            0
        );
        tooltip.show();
        this.waitForTimeout(() => tooltip.hide(), 1200);
    }

    /**
     * This function will make the RPC call to add the guests from there email,
     * if a guest is unavailable then it will give us an error msg on the UI side with
     * the name of the unavailable guest.
     */
    async onGuestAdd() {
        const guestEmails = this.el.querySelector("#o_appointment_input_guest_emails").value;
        const accessToken = this.el.querySelector("#access_token").value;
        const emailInfo = findInvalidEmailFromText(guestEmails);
        if (emailInfo.emailList.length > 10) {
            this.errorMessage = _t("You cannot invite more than 10 people");
        } else if (emailInfo.invalidEmails.length) {
            this.errorMessage = _t("Invalid Email");
        } else {
            this.errorMessage = "";
            await rpc(`/calendar/${accessToken}/add_attendees_from_emails`, {
                access_token: accessToken,
                emails_str: guestEmails,
            });
            location.reload();
        }
    }

    /**
     * This function displays a textarea on the appointment validation page,
     * allowing users to enter guest emails if the allow_guest option is enabled.
     */
    onGuestAdditionOpen() {
        this.showGuestAddition = true;
        this.updateContent();
        this.el.querySelector("#o_appointment_input_guest_emails").focus();
    }

    /**
     * This function will clear the guest email textarea at the appointment validation page
     * if allow_guest option is enabled.
     */
    onGuestDiscard() {
        this.showGuestAddition = false;
        this.el.querySelector("#o_appointment_input_guest_emails").value = "";
    }
}

registry
    .category("public.interactions")
    .add("appointment.appointment_validation", AppointmentValidation);
