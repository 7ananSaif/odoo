import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

export class AppointmentBookingActionHelper extends Component {
    static template = "appointment.AppointmentBookingActionHelper";
    static props = ["context", "onNewClicked"];
    setup() {
        this.action = useService("action");
    }

    async openShareDialog() {
        this.action.doAction({
            name: 'Create a Share Link',
            type: 'ir.actions.act_window',
            res_model: 'appointment.invite',
            views: [[false, 'form']],
            target: 'new',
            context: {
                'default_appointment_type_ids': [this.props.context.default_appointment_type_id],
                'dialog_size': 'medium',
            },
        });
    }
};
