import {
    AttachmentPreviewListController,
    AttachmentPreviewListRenderer,
} from "../../attachment_preview_list_view/attachment_preview_list_view";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { useChildSubEnv } from "@odoo/owl";
import { makeActiveField } from "@web/model/relational_model/utils";

export class BankRecListController extends AttachmentPreviewListController {
    setup() {
        super.setup(...arguments);

        this.skipKanbanRestore = {};

        useChildSubEnv({
            skipKanbanRestoreNeeded: (stLineId) => this.skipKanbanRestore[stLineId],
        });
    }

    /**
     * Override
     * Don't allow bank_rec_form to be restored with previous values since the statement line has changed.
     */
    async onRecordSaved(record) {
        this.skipKanbanRestore[record.resId] = true;
        return super.onRecordSaved(...arguments);
    }

    get previewerStorageKey() {
        return "account.statement_line_pdf_previewer_hidden";
    }

    get modelParams() {
        const params = super.modelParams;
        params.config.activeFields.bank_statement_attachment_ids = makeActiveField();
        params.config.activeFields.bank_statement_attachment_ids.related = {
            fields: {
                mimetype: { name: "mimetype", type: "char" },
            },
            activeFields: {
                mimetype: makeActiveField(),
            },
        };
        params.config.activeFields.attachment_ids = makeActiveField();
        params.config.activeFields.attachment_ids.related = {
            fields: {
                mimetype: { name: "mimetype", type: "char" },
            },
            activeFields: {
                mimetype: makeActiveField(),
            },
        };
        return params;
    }

    async setSelectedRecord(accountBankStatementLineData) {
        this.attachmentPreviewState.selectedRecord = accountBankStatementLineData;
        if (accountBankStatementLineData.data?.attachment_ids.count) {
            await this.setThread(accountBankStatementLineData, "attachment_ids", "move_id");
        } else {
            await this.setThread(
                accountBankStatementLineData,
                "bank_statement_attachment_ids",
                "statement_id"
            );
        }
    }
}

export class BankRecListRenderer extends AttachmentPreviewListRenderer {}

export const bankRecListView = {
    ...listView,
    Controller: BankRecListController,
    Renderer: BankRecListRenderer,
};

registry.category("views").add("bank_rec_list", bankRecListView);
