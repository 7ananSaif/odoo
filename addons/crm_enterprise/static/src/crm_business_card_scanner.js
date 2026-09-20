import { Component } from "@odoo/owl";

import { FileUploader } from "@web/views/fields/file_handler";
import { useService } from "@web/core/utils/hooks";
import { isMobileOS } from "@web/core/browser/feature_detection";


export class CrmBusinessCardScanner extends Component {
    static template = "crm_enterprise.CrmBusinessCardScanner";
    static components = {
        FileUploader,
    };
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.businessCardsAttachmentsIds = [];
        this.isMobileOS = isMobileOS();
    }

    async onFileUploaded(file) {
        const attachmentData = {
            name: file.name,
            type: 'binary',
            mimetype: file.type,
            datas: file.data,
        };
        this.env.services.ui.block();
        try {
            const [attachmentId] = await this.orm.create("ir.attachment", [attachmentData]);
            await this.orm.call(
                "ir.attachment",
                "generate_access_token",
                [attachmentId]
            );
            this.businessCardsAttachmentsIds.push(attachmentId);
        } finally {
            this.env.services.ui.unblock();
        }
    }

    async onUploadComplete() {
        this.env.services.ui.block();
        try {
            const actionValues = await this.orm.call(
                "crm.lead",
                "action_ocr_business_cards",
                [[], this.businessCardsAttachmentsIds]
            );
            if (actionValues) {
                this.action.doAction(actionValues);
            }
        } finally {
            this.businessCardsAttachmentsIds = [];
            this.env.services.ui.unblock();
        }
    }
}
