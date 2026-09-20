import { registry } from "@web/core/registry";
import { ListRenderer } from "@web/views/list/list_renderer";
import { AccountFileUploader } from "@account/components/account_file_uploader/account_file_uploader";
import { UploadDropZone } from "@account/components/upload_drop_zone/upload_drop_zone";
import {
    bankRecListView,
    BankRecListController,
    BankRecListRenderer,
} from "@account_accountant/components/bank_reconciliation/list_view/list";
import { useState } from "@odoo/owl";

const synchronizedModes = ["online_sync", "l10n_be_codabox"]

export class BankRecListUploadController extends BankRecListController {
    static components = {
        ...BankRecListController.components,
        AccountFileUploader,
    };

    get showUploadButton() {
        return !synchronizedModes.includes(this.props.context?.bank_statements_source);
    }
}

export class BankRecListUploadRenderer extends BankRecListRenderer {
    static template = "account.BankRecListUploadRenderer";
    static components = {
        ...ListRenderer.components,
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

export const bankRecListUploadView = {
    ...bankRecListView,
    Controller: BankRecListUploadController,
    Renderer: BankRecListUploadRenderer,
    buttonTemplate: "account.BankRecListUploadButtons",
};

registry.category("views").add("bank_rec_list", bankRecListUploadView, { force: true });
