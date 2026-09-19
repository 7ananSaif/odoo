import { AccountFileUploader } from "@account/components/account_file_uploader/account_file_uploader";
import { BankRecKanbanController } from "@account_accountant/components/bank_reconciliation/kanban_controller";
import {
    BankRecKanbanRenderer,
    BankRecKanbanView,
} from "@account_accountant/components/bank_reconciliation/kanban_renderer";
import { UploadDropZone } from "@account/components/upload_drop_zone/upload_drop_zone";
import { registry } from "@web/core/registry";
import { useState } from "@odoo/owl";

const synchronizedModes = ["online_sync", "l10n_be_codabox"]

export class BankRecKanbanUploadController extends BankRecKanbanController {
    static components = {
        ...BankRecKanbanController.components,
        AccountFileUploader,
    };

    get showUploadButton() {
        return !synchronizedModes.includes(this.props.context?.bank_statements_source);
    }
}

export class BankRecKanbanUploadRenderer extends BankRecKanbanRenderer {
    static components = {
        ...BankRecKanbanRenderer.components,
        UploadDropZone,
    };

    setup() {
        super.setup();
        this.dropzoneState = useState({ visible: false });
    }

    onDragStart(ev) {
        if (ev.dataTransfer.types.includes("Files")) {
            this.dropzoneState.visible = true;
        }
    }

    get showUploadButton() {
        return !synchronizedModes.includes(this.env.model.config.context?.bank_statements_source);
    }
}

export const bankRecKanbanUploadView = {
    ...BankRecKanbanView,
    Controller: BankRecKanbanUploadController,
    Renderer: BankRecKanbanUploadRenderer,
    buttonTemplate: "account_accountant.BankRecoKanbanUploadButton",
};

registry.category("views").add("bank_rec_widget_kanban", bankRecKanbanUploadView, { force: true });
