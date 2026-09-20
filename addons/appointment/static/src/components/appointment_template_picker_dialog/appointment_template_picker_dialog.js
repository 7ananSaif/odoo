import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart } from "@odoo/owl";

/**
 * This component will display an appointment template picker.
 * When using the create button in form / kanban / list views,
 * The dialog will open and on selection an appointment type
 * will be created with the template values, and its form view opened.
 */
export class AppointmentTemplatePickerDialog extends Component {
    static template = "appointment.AppointmentTemplatePickerDialog";
    static components = { Dialog };
    static props = {
        close: Function,
    };
    setup() {
        super.setup();
        this.action = useService("action");
        this.orm = useService("orm");

        onWillStart(async () => {
            this.appointmentTypeTemplatesData = await this.orm.call(
                'appointment.type',
                'get_appointment_type_templates_data',
                []
            );
        });
    }

    async onTemplateClick(templateData) {
        const action = await this.orm.call(
            'appointment.type',
            'action_setup_appointment_type_template',
            [templateData.template_key],
        );
        this.action.doAction(action);
    }
}
