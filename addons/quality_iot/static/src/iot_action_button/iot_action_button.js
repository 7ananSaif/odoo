import { Component } from "@odoo/owl";
import { useService } from '@web/core/utils/hooks';
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

/**
 * Base class for IoT action buttons in quality checks.
 * Meant to add a button in the modal footer of quality checks
 * when triggered from manufacturing app (not shop floor).
 */
export class IotActionButton extends Component {
    static template = "quality_iot.iotActionButton";
    static props = {
        ...standardWidgetProps,
        btn_name: String,
    }

    setup() {
        super.setup();
        this.dialog = useService('dialog');
        this.notification = useService('notification');
        this.iotHttpService = useService('iot_http');
    }

    get iotDevice() {
        return {
            iotBoxId: this.props.record.data.iot_box_id.id,
            deviceIdentifier: this.props.record.data.identifier,
        }
    }

    async onClick() {
        throw new Error("onClick method must be implemented by subclasses");
    }
}
