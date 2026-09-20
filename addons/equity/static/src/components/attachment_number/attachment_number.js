import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class AttachmentNumber extends Component {
    // TODO: copied from hr_expense.AttachmentNumber (can be moved to web and used in both modules later)
    static template = "equity.AttachmentNumber";
    static props = { ...standardFieldProps };

    setup() {
        super.setup();
        this.attachment_number = this.props.record.data.attachment_number
    }
}

registry.category("fields").add("attachment_number", { component: AttachmentNumber });
