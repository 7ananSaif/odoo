import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { computeM2OProps, Many2One } from "@web/views/fields/many2one/many2one";
import { buildM2OFieldDescription, Many2OneField } from "@web/views/fields/many2one/many2one_field";

export class DocumentsFolderMany2One extends Component {
    static template = "documents.DocumentsFolderMany2One";
    static components = { Many2One };
    static props = { ...Many2OneField.props };

    setup() {
        this.action = useService("action");
    }

    get m2oProps() {
        return {
            ...computeM2OProps(this.props),
            openRecordAction: () => this.openAction(),
        };
    }

    /**
     * Open the documents kanban/list view, in the folder instead of redirecting to the form view.
     */
    async openAction() {
        const value = this.props.record.data[this.props.name];
        await this.action.doAction("documents.document_action_preference", {
            additionalContext: {
                no_documents_unique_folder_id: true,
                searchpanel_default_user_folder_id: value && value.id.toString(),
            },
        });
    }
}

registry.category("fields").add("documents_folder_many2one", {
    ...buildM2OFieldDescription(DocumentsFolderMany2One),
});
