import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { FileUploader } from "@web/views/fields/file_handler";

class CustomAccountReturnFileUploaderComponent extends FileUploader {
    static template = "account_reports.CustomAccountReturnFileUploaderComponent"
}

class AccountReturnCheckFileUploader extends Component {
    static template = "account_reports.AccountReturnCheckFileUploader";
    static components = {
        FileUploader: CustomAccountReturnFileUploaderComponent
    };
    static props = {
        ...standardWidgetProps,
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.attachmentIds = [];
    }

    async onFileUploaded(file) {
        const att_data = {
            name: file.name,
            mimetype: file.type,
            datas: file.data,
            res_model: this.props.record.resModel,
            res_id: this.props.record.resId,
        };
        const [att_id] = await this.orm.create(
            "ir.attachment",
            [att_data],
            { context: this.props.record.context}
        );
        this.attachmentIds.push(att_id);
    }

    async onUploadCompleted() {
        await this.orm.write(this.props.record.resModel, [this.props.record.resId], { attachment_ids: this.attachmentIds });
        this.attachmentIds = [];
        this.props.record.model.load();
    }

    async onClick(event) {
        console.log("uploader")
        console.log(event.target);
        event.stopPropagation();
    }
}

export const accountReturnCheckFileUploader = {
    component: AccountReturnCheckFileUploader,
}

registry.category("view_widgets").add("account_return_check_file_uploader", accountReturnCheckFileUploader)
