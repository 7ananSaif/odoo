import { omit } from "@web/core/utils/objects";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";

import { Component, toRaw } from "@odoo/owl";

export class DocumentsDetailsMany2OneField extends Component {
    static components = { Many2OneField };
    static props = {
        ...Many2OneField.props,
        readonlyPlaceholder: Many2OneField.props.placeholder,
    };
    static template = "documents.DocumentsDetailsMany2One";

    get value() {
        return toRaw(this.props.record.data[this.props.name]);
    }

    get fieldProps() {
        return omit(this.props, "readonlyPlaceholder");
    }
}
