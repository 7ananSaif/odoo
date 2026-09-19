import { patch } from "@web/core/utils/patch";
import { AppointmentForm } from "@appointment/interactions/appointment_form";
import { ReCaptcha } from "@google_recaptcha/js/recaptcha";
import { session } from "@web/session";


patch(AppointmentForm.prototype, {
    setup(){
        super.setup();
        this.recaptcha = new ReCaptcha();
        this.notification = this.services.notification;
        // dynamic get rather than import as we don't depend on this module
        if (session.turnstile_site_key) {
            const { TurnStile } = odoo.loader.modules.get(
                "@website_cf_turnstile/interactions/turnstile"
            );
            if (TurnStile) {
                this._turnstile = new TurnStile("appointment_form_submission");
                this._turnstile.turnstileEl.classList.add("float-start");
            }
        }
    },

    async willStart(){
        this.recaptcha.loadLibs();
        this.addTurnstile(document.querySelector("form.appointment_submit_form"));
        await super.willStart();
    },

    /**
     * add recaptcha before submitting
     *
     * @override
     */
    async onConfirmAppointment(ev){
        const button = ev.target;
        const form = button.closest("form");
        if (!(await this.addRecaptchaToken(form))) {
            button.setAttribute("disabled", true);
            setTimeout(() => button.removeAttribute("disabled"), 2000);
        } else {
            super.onConfirmAppointment.call(this, ...arguments);
        }
    },

    /**
     * Add an input containing the recaptcha token if relevant
     *
     * @returns {boolean} false if form submission should be cancelled otherwise true
     */
    async addRecaptchaToken(form) {
        const tokenObj = await this.recaptcha.getToken("appointment_form_submission");
        if (tokenObj.error) {
            this.notification.add(tokenObj.error, {
                sticky: true,
                type: "danger",
            });
            return false;
        } else if (tokenObj.token) {
            const recaptchaTokenInput = document.createElement("input");
            recaptchaTokenInput.setAttribute("name", "recaptcha_token_response");
            recaptchaTokenInput.setAttribute("type", "hidden");
            recaptchaTokenInput.setAttribute("value", tokenObj.token);
            form.appendChild(recaptchaTokenInput);
        }
        return true;
    },

    addTurnstile(form) {
        if (!this._turnstile) {
            return false;
        }

        const submitButton = form.querySelector("button.o_appointment_form_confirm_btn");
        this._turnstile.constructor.disableSubmit(submitButton);
        submitButton.after(this._turnstile.turnstileEl);
        this._turnstile.insertScripts(form);
        this._turnstile.render();

        return true;
    },
});

