class AppointmentCrmSteps {

    _goToAppointment(name) {
        /**
         * This method exists to be overridden as the steps to go to the
         * appointment change in sub-modules.
         * @param {String} name - The name of the appointment
         */
        return [
            {
                content: "Select the appointment.",
                trigger: "#appointment_type_id",
                run: `selectByLabel ${name}`,
            },
            {
                content: "Confirm the selection.",
                trigger: ".o_appointment_select_button",
                run: "click",
                expectUnloadPage: true,
            },
        ];
    }
}

export default AppointmentCrmSteps;
