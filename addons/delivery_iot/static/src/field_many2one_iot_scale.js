import { Component } from "@odoo/owl";
import { registry } from '@web/core/registry';
import { computeM2OProps, Many2One } from "@web/views/fields/many2one/many2one";
import { useIotDevice } from '@iot/iot_device_hook';
import {
    buildM2OFieldDescription,
    extractM2OFieldProps,
    Many2OneField,
} from "@web/views/fields/many2one/many2one_field";

export class FieldMany2OneIoTScale extends Component {
    static template = 'delivery_iot.FieldMany2OneIoTScale';
    static components = { Many2One };
    static props = {
        ...Many2OneField.props,
        manual_measurement_field: { type: String },
        ip_field: { type: String },
        identifier_field: { type: String },
        value_field: { type: String },
    };
    setup() {
        this.getIotDevice = useIotDevice({
            getIotIp: () => this.props.record.data[this.props.ip_field],
            getIdentifier: () => this.props.record.data[this.props.identifier_field],
            onValueChange: (data) => this.props.record.update({ [this.props.value_field]: data.value }),
            onStartListening: () => {
                if (this.getIotDevice() && !this.manualMeasurement) {
                    this.getIotDevice().action({ action: 'start_reading' });
                }
            },
            onStopListening: () => {
                if (this.getIotDevice() && !this.manualMeasurement) {
                    this.getIotDevice().action({ action: 'stop_reading' });
                }
            }
        });
    }

    get m2oProps() {
        return computeM2OProps(this.props);
    }
    get showManualReadButton() {
        return this.getIotDevice() && this.manualMeasurement && this.env.model.root.isInEdition;
    }
    get manualMeasurement() {
        return this.props.record.data[this.props.manual_measurement_field];
    }
    onClickReadWeight() {
        return this.getIotDevice().action({ action: 'read_once' });
    }
}

registry.category("fields").add("field_many2one_iot_scale", {
    ...buildM2OFieldDescription(FieldMany2OneIoTScale),
    extractProps({ options }) {
        const props = extractM2OFieldProps(...arguments);
        props.manual_measurement_field = options.manual_measurement_field;
        props.ip_field = options.ip_field;
        props.identifier_field = options.identifier;
        props.value_field = options.value_field;
        return props;
    },
});
