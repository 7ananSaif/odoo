import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class DocumentsDiscardChangesField extends Component {
    static template = "documents.DocumentsDiscardChangesField";
    static props = { ...standardFieldProps };

    async discard() {
        this.props.record.model.root.discard();
    }
}

export const documentsDiscardChangesField = { component: DocumentsDiscardChangesField };

registry.category("fields").add("documents_discard_changes", documentsDiscardChangesField);
