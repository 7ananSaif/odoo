import { FileViewer as WebFileViewer } from "@web/core/file_viewer/file_viewer";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { useComponent, onWillStart } from "@odoo/owl";


patch(WebFileViewer.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        const component = useComponent();
        this.action = component.env.services?.action;

        onWillStart(async () => {
            const fileThread = this.state.file?.thread;
            this.allowSignTemplateCreation = fileThread && fileThread.model !== "sign.request";
            this.hasUserAccess = await user.hasGroup("sign.group_sign_user");
        });
    },

    async openSignTemplate() {
        const file = this.state.file;

        // Need res_id or res_model to reference to the sign request
        let { model: res_model, id: res_id } = file.thread;
        const attachment_id = file.id;

        // If the res_model is sign.request as it's not allowed in reference field selection in the backend,
        if (res_model === 'sign.request' || !res_id || !res_model) {
            return;
        }

        const [template_id, template_name] = await this.orm.call(
            "sign.template",
            "create_sign_template_from_ir_attachment_data",
            [attachment_id, res_id, res_model],
        );

        this.action.doAction({
            type: "ir.actions.client",
            tag: "sign.Template",
            name: `Template ${template_name}`,
            params: {
                id: template_id,
                sign_directly_without_mail: false,
            },
            context: {
                default_reference_doc: `${res_model},${res_id}`,
            },
        });
    },
});
