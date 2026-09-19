import { useService } from '@web/core/utils/hooks';
import { Component, onWillStart } from '@odoo/owl';

export class AppointmentTypeActionHelper extends Component {
    static template = 'appointment.AppointmentTypeActionHelper';
    static props = {};

    setup() {
        this.orm = useService('orm');
        this.action = useService('action');

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
};
