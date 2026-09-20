import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { DESTINATION_MAX_LENGTH, truncate } from "@documents/views/widget/utils";
import { AccessRightsUpdateConfirmationDialog } from "@documents/owl/components/access_update_confirmation_dialog/access_update_confirmation_dialog";

export class DocumentsOperationConfirmation extends Component {
    static template = "documents.DocumentsOperationConfirmation";
    static props = { ...standardWidgetProps };

    setup() {
        super.setup();
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.orm = useService("orm");
    }

    get buttonLabel() {
        const destination = {
            folder_name: truncate(this.props.record.data.display_name, DESTINATION_MAX_LENGTH),
        };
        if (this.props.record.data.user_permission !== "edit") {
            return _t("Insufficient access to %(folder_name)s", destination);
        }
        if (this.props.record.data.operation === "shortcut") {
            if (this.isMultiDocuments) {
                return _t("Create shortcuts in %(folder_name)s", destination);
            }
            return _t("Create a shortcut in %(folder_name)s", destination);
        } else if (this.props.record.data.operation === "add") {
            return _t("Add in %(folder_name)s", destination);
        } else if (this.props.record.data.operation === "copy") {
            return _t("Duplicate in %(folder_name)s", destination);
        } else if (this.props.record.data.operation === "move") {
            return _t("Move to %(folder_name)s", destination);
        }
        return _t("Confirm");
    }

    async onClick() {
        if (!this.props.record.resId) {
            const recordSaved = await this.props.record.save();
            if (!recordSaved) {
                return;
            }
        }
        if (this.needsConfirmation) {
            const confirmed = await new Promise((resolve) => {
                this.dialog.add(AccessRightsUpdateConfirmationDialog, {
                    destinationFolder: {
                        display_name: this.props.record.data.display_name,
                        access_internal: this.props.record.data.access_internal,
                        access_via_link: this.props.record.data.access_via_link,
                        is_access_via_link_hidden: this.props.record.data.is_access_via_link_hidden,
                    },
                    confirm: async () => resolve(true),
                    cancel: () => resolve(false),
                });
            });
            if (!confirmed) {
                return;
            }
        }
        await this.orm.call("documents.operation", "action_confirm", [this.props.record.resId]);
        this.notifySuccess();
        this.env.dialogData.close();
    }

    get needsConfirmation() {
        if (
            this.props.record.data.operation !== "move" ||
            isNaN(this.props.record.data.destination) ||
            !this.props.record.data.document_ids.records.length
        ) {
            return false;
        }
        for (const doc of this.props.record.data.document_ids.records) {
            if (
                doc.data.access_internal !== this.props.record.data.access_internal ||
                doc.data.access_via_link !== this.props.record.data.access_via_link ||
                doc.data.is_access_via_link_hidden !==
                    this.props.record.data.is_access_via_link_hidden
            ) {
                return true;
            }
        }
        return false;
    }

    notifySuccess() {
        const destination = { folder_name: this.props.record.data.display_name };
        let message = "";
        if (this.props.record.data.operation === "shortcut") {
            if (this.isMultiDocuments) {
                message = _t("Shortcuts created in %(folder_name)s!", destination);
            } else {
                message = _t("Shortcut created in %(folder_name)s!", destination);
            }
        } else if (this.props.record.data.operation === "move") {
            if (this.isMultiDocuments) {
                message = _t("Documents moved to %(folder_name)s!", destination);
            } else {
                message = _t("Document moved to %(folder_name)s!", destination);
            }
        } else if (["add", "copy"].includes(this.props.record.data.operation)) {
            if (this.isMultiDocuments) {
                message = _t("Documents created in %(folder_name)s!", destination);
            } else {
                message = _t("Document created in %(folder_name)s!", destination);
            }
        }
        this.notification.add(message, { title: _t("Done"), type: "success" });
    }

    get isMultiDocuments() {
        return this.props.record.data.document_ids.records.length > 1;
    }
}

export const documentsOperationConfirmation = {
    component: DocumentsOperationConfirmation,
    fieldDependencies: [
        { name: "display_name", type: "char" },
        { name: "destination", type: "char" },
        { name: "document_ids", type: "many2many" },
        { name: "operation", type: "char" },
    ],
};

registry
    .category("view_widgets")
    .add("documents_operation_confirmation", documentsOperationConfirmation);
