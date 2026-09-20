import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { useService } from "@web/core/utils/hooks";
import { useX2ManyCrud } from "@web/views/fields/relational_utils";

import { SelectAddDocumentCreateDialog } from "@documents/views/view_dialogs/select_add_document_create_dialog";

export class MailComposerDocumentSelector extends Component {
    static template = "documents.MailComposerDocumentSelector";
    static props = { ...standardWidgetProps };

    setup() {
        this.dialogService = useService("dialog");
        this.operations = useX2ManyCrud(() => this.props.record.data["attachment_ids"], true);
    }

    saveRecordHandler = async (idArray) => {
        await this.operations.saveRecord(idArray);
    };

    addDocumentsAttachment = () => {
        const { data } = this.props.record;
        const resId = this.props.record.resId || JSON.parse(data.res_ids)?.[0];
        const model = data.model;
        this.dialogService.add(SelectAddDocumentCreateDialog, {
            resModel: "documents.document",
            title: _t("Search: Documents"),
            noCreate: true,
            domain: [
                ["type", "=", "binary"],
                ["shortcut_document_id", "=", false],
            ],
            context: {
                list_view_ref: "documents.documents_view_list_add_documents_attachment",
                documents_search_panel_no_trash: true,
                documents_view_secondary: true,
            },
            chatterParams: {
                model,
                resId,
                isFromFullComposer: true,
                saveRecordHandler: this.saveRecordHandler,
                addDocumentsBus: this.env.model.bus,
            },
        });
    };
}

export const mailComposerDocumentSelector = {
    component: MailComposerDocumentSelector,
};

registry
    .category("view_widgets")
    .add("mail_composer_document_selector", mailComposerDocumentSelector);
