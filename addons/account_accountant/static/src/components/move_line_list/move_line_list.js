import { AttachmentPreviewListController, AttachmentPreviewListRenderer } from "../attachment_preview_list_view/attachment_preview_list_view";

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { makeActiveField } from "@web/model/relational_model/utils";

export class AccountMoveLineListController extends AttachmentPreviewListController {
    get previewerStorageKey() {
        return "account.move_line_pdf_previewer_hidden";
    }

    get modelParams() {
        const params = super.modelParams;
        params.config.activeFields.move_attachment_ids = makeActiveField();
        params.config.activeFields.move_attachment_ids.related = {
            fields: {
                mimetype: { name: "mimetype", type: "char" },
            },
            activeFields: {
                mimetype: makeActiveField(),
            },
        };
        return params;
    }

    async setSelectedRecord(accountMoveLineData) {
        this.attachmentPreviewState.selectedRecord = accountMoveLineData;
        await this.setThread(accountMoveLineData, "move_attachment_ids", "move_id");
    }
}

export class AccountMoveLineListRenderer extends AttachmentPreviewListRenderer {}

export const AccountMoveLineListView = {
    ...listView,
    Renderer: AccountMoveLineListRenderer,
    Controller: AccountMoveLineListController,
};

registry.category("views").add("account_move_line_list", AccountMoveLineListView);
