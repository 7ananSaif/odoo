import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { computeM2OProps, Many2One } from "@web/views/fields/many2one/many2one";
import { buildM2OFieldDescription, Many2OneField } from "@web/views/fields/many2one/many2one_field";

export class AppointmentTypeSyncDuration extends Component {
    static template = "appointment.AppointmentTypeSyncDuration";
    static components = { Many2One };
    static props = { ...Many2OneField.props };

    setup() {
        this.orm = useService("orm");

        this.appointmentTypeId = this.props.record.data.appointment_type_id.id;
        this.isDefaultDuration = false;

        onWillStart(async () => {
            if (this.appointmentTypeId) {
                const appointmentDuration = await this.orm.read(
                    "appointment.type", [this.appointmentTypeId], ['appointment_duration']
                );
                this.isDefaultDuration = this.props.record.data.duration === appointmentDuration?.[0].appointment_duration;
            }
        });

        useRecordObserver(async (record) => {
            if (record.data.appointment_type_id.id !== this.appointmentTypeId && this.isDefaultDuration) {
                this.appointmentTypeId = record.data.appointment_type_id.id;
                if (this.appointmentTypeId) {
                    const appointmentDuration = await this.orm.read(
                        "appointment.type", [this.appointmentTypeId], ['appointment_duration']
                    );
                    if (appointmentDuration.length !== 0) {
                        record.update({'duration': appointmentDuration[0].appointment_duration});
                    }
                }
            }
        });
    }

    get m2oProps() {
        return computeM2OProps(this.props);
    }
}

registry.category("fields").add("appointment_type_sync_duration", {
    ...buildM2OFieldDescription(AppointmentTypeSyncDuration),
    fieldDependencies: [{ name: "appointment_type_id", type: "many2one" }],
});
