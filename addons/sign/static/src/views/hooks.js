import { _t } from "@web/core/l10n/translation";
import { useService, useBus } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { TemplateAlertDialog } from "@sign/backend_components/template_alert_dialog/template_alert_dialog";
import { onWillStart, useComponent, useRef, useEnv } from "@odoo/owl";

export function useSignViewButtons() {
    const component = useComponent();
    const fileInput = useRef("uploadFileInput");
    const orm = useService("orm");
    const dialog = useService("dialog");
    const action = useService("action");
    const env = useEnv();

    onWillStart(async () => {
        component.isSignUser = await user.hasGroup("sign.group_sign_user");
    });

    let latestRequestContext;
    let inactive;
    let resModel;
    let signTemplateId = false;
    let referenceDoc;
    let activityId;
    let updateDocuments = () => {};

    const uploadFiles = async (files) => {
        inactive = resModel === 'sign.template' ? true : false;
        const files_list = await Promise.all(
            Array.from(files).map(async (file) => ({
                name: file.name,
                datas: (await getDataURLFromFile(file)).split(",")[1],
            }))
        );
        const context = user.context;
        if (referenceDoc) {
            const modelName = referenceDoc.split(',')[0];
            context['default_model_name'] = modelName;
        }
        if (signTemplateId) {
            return await orm.call(
                "sign.template",
                "update_from_attachment_data",
                [signTemplateId],
                { attachment_data_list: files_list, context: context },
            );
        } else {
            return await orm.call("sign.template", "create_from_attachment_data",
                [files_list, inactive],
                {context: context}
            );
        }
    };

    const upload = {
        /**
         * Handles the template file upload logic.
         */
        onFileInputChange: async (ev) => {
            const files = ev?.type === "change" ? ev.target.files : ev.detail.files;
            if (!files || !files.length) {
                return;
            }
            if (Array.from(files).filter((file) => file.type !== "application/pdf").length) {
                dialog.add(TemplateAlertDialog, {
                    title: _t("File Error"),
                    body: _t("Only PDF files are allowed."),
                });
                return;
            }
            if (signTemplateId) {
                await uploadFiles(files);
                return updateDocuments();
            }
            const {
                id: template_id,
                name: template_name,
            } = await uploadFiles(files);
            action.doAction({
                type: "ir.actions.client",
                tag: "sign.Template",
                name: template_name,
                params: {
                    sign_edit_call: latestRequestContext,
                    id: template_id,
                    sign_directly_without_mail: false,
                    resModel: resModel,
                },
                context: {
                    default_reference_doc: referenceDoc,
                    default_activity_id: activityId,
                },
            });
        },

        /**
        * Initiates the file upload process by opening a file input dialog
        * and configuring the 'save as template' button based on the provided model
        * and other properties.
        *
        * @param {Object}
        */
        requestFile(context) {
            latestRequestContext = context;
            resModel = this.props.resModel;
            signTemplateId = this.props.signTemplateId;
            updateDocuments = this.props.updateDocuments;
            referenceDoc = this.env.searchModel?.globalContext?.default_reference_doc;
            activityId = this.env.searchModel?.globalContext?.default_activity_id;
            fileInput.el.click();
        },
    };

    useBus(env.bus, "change_file_input", async (ev) => {
        if (component.constructor.name === 'SignActionHelper') {
            // Skip processing in SignActionHelper(signRenderer) call to prevent double handling
            // because its triggered from signController too.
            return;
        }
        fileInput.el.files = ev.detail.files;
        resModel = ev.detail.resModel;
        await upload.onFileInputChange(ev);
    });

    return upload
}
