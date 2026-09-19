import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { SignTemplateIframe } from "./sign_template_iframe";
import { Component, useRef, useEffect, onWillUnmount, onWillStart, useState, useExternalListener } from "@odoo/owl";
import { buildPDFViewerURL , injectPDFCustomStyles } from "@sign/components/sign_request/utils";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { hidePDFJSButtons } from "@web/core/utils/pdfjs";
import { SignSaveTemplateDialog } from "./sign_save_template_dialog";
import { user } from "@web/core/user";


export class SignTemplateBody extends Component {
    static template = "sign.SignTemplateBody";
    static components = {
        SignSaveTemplateDialog,
    };
    static props = {
        signItemTypes: { type: Array },
        signItems: { type: Array, optional: true },
        signRoles: { type: Array },
        radioSets: { type: Object, optional: true },
        hasSignRequests: { type: Boolean },
        signItemOptions: { type: Array },
        attachmentLocation: { type: String },
        signTemplate: { type: Object },
        goBackToKanban: { type: Function },
        onTemplateSaveClick: { type: Function },
        manageTemplateAccess: { type: Boolean },
        resModel: { type: String },
        signStatus: { type: Object },
        iframe: { type: Object, optional: true },
        setIframe: { type: Function },
        documentId: { type: Number },
        updateSignItemsCountCallback: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.popover = useService("popover");
        this.dialog = useService("dialog");
        this.PDFIframe = useRef("PDFIframe");
        this.action = useService("action");
        this.PDFViewerURL = buildPDFViewerURL(this.props.attachmentLocation, this.env.isSmall);
        this.props.signStatus.discardChanges = this.discardChanges.bind(this);
        this.state = useState({
            documentUsedTimesCounter: 0,
        })
        useEffect(
            (el) => {
                if (el) {
                    hidePDFJSButtons(el, {
                        hideDownload: true,
                        hidePrint: true,
                        hidePresentation: true,
                        hideRotation: true,
                    });
                }
            },
            () => [this.PDFIframe.el]
        );
        useEffect(
            () => {
                return this.waitForPDF();
            },
            () => []
        );

        useExternalListener(document, "visibilitychange", () => {
            if (document.visibilityState === "hidden") {
                this.props.signStatus.save();
            }
        });


        onWillUnmount(() => {
            if (this.props.iframe) {
                this.props.iframe.unmount();
                this.props.iframe = null;
            }
        });

        onWillStart(async () => {
            if (!this.props.signTemplate.active) {
                /* When uploading a PDF for signing, we check how many times a PDF with that
                name was used and if it is bigger than two, then suggest the user saving it
                as template with in a notification with a button. */
                const documentUsedTimes = await this.orm.searchCount(
                    "sign.request",
                    [["reference", "ilike", this.props.signTemplate.display_name]]
                );
                this.state.documentUsedTimesCounter = documentUsedTimes;
            };

            return await Promise.all([this.fetchRadioSets(), this.fetchSignItemData()]);
        });
    }

    async fetchRadioSets() {
        this.radioSets = await this.orm.call(
            "sign.document",
            "get_radio_sets_dict", [
                this.props.documentId,
            ]
        );
    }

    async fetchSignItemData() {
        this.signItems = await this.orm.call(
            "sign.item",
            "search_read",
            [[["document_id", "=", this.props.documentId]]],
            { context: user.context }
        );

        this.signItems.forEach((item) => {
            item.radio_set_id = item?.radio_set_id[0] || undefined;
            item.roleName = item.responsible_id[1];
            item.document_id = item.document_id[0];
        });
    }

    waitForPDF() {
        this.PDFIframe.el.onload = () => {
            injectPDFCustomStyles(this.PDFIframe.el.contentDocument);
            setTimeout(() => this.doPDFPostLoad(), 1);
        };
    }

    async discardChanges() {
        const { signTemplate } = this.props;
        const templateName = signTemplate.display_name;
        const templateId = parseInt(signTemplate.id, 10);
        this.props.signStatus.isTemplateChanged = false;
        this.props.signStatus.isDiscardingChanges = true;
        await this.action.doAction({
            type: "ir.actions.client",
            tag: "sign.Template",
            name: _t("Template %s", templateName),
            params: {
                id: templateId,
            },
        }, {
            stackPosition: "replaceCurrentAction"
        });
    }

    doPDFPostLoad() {
        this.preventDroppingImagesOnViewerContainer();
        const iframe = new SignTemplateIframe(
            this.PDFIframe.el.contentDocument,
            this.env,
            {
                orm: this.orm,
                popover: this.popover,
                dialog: this.dialog,
                notification: this.notification,
            },
            {
                signItemTypes: this.props.signItemTypes,
                signItems: this.signItems,
                signRoles: this.props.signRoles,
                hasSignRequests: this.props.hasSignRequests,
                signItemOptions: this.props.signItemOptions,
                radioSets: this.radioSets,
                saveTemplate: () => this.saveTemplate(),
                getRadioSetInfo: (id) => this.getRadioSetInfo(id),
                rotatePDF: () => this.rotatePDF(),
                signStatus: this.props.signStatus,
                setTemplateChangedState: (state) => this.props.signStatus.isTemplateChanged = state,
                documentId: this.props.documentId,
                updateSignItemsCountCallback: this.props.updateSignItemsCountCallback,
            }
        );
        this.props.setIframe(iframe);
    }

    /**
     * Prevents opening files in the pdf js viewer when dropping files/images to the viewerContainer
     * Ref: https://stackoverflow.com/a/68939139
     */
    preventDroppingImagesOnViewerContainer() {
        const viewerContainer = this.PDFIframe.el.contentDocument.querySelector("#viewerContainer");
        viewerContainer.addEventListener(
            "drop",
            (e) => {
                if (e.dataTransfer.files && e.dataTransfer.files.length) {
                    e.stopImmediatePropagation();
                    e.stopPropagation();
                }
            },
            true
        );
    }

    async saveTemplate(newTemplateName) {
        const [updatedSignItems, Id2UpdatedItem] = this.prepareTemplateData();
        const newId2ItemIdMap = await this.orm.call("sign.template", "update_from_pdfviewer", [
            this.props.signTemplate.id,
            updatedSignItems,
            this.props.iframe?.deletedSignItemIds,
            newTemplateName || "",
        ]);

        if (!newId2ItemIdMap) {
            // updatedSignItems returns {} if there are no changes to be saved.
            // In this case, we don't need to show the dialog.
            if (updatedSignItems && Object.keys(updatedSignItems).length > 0) {
                this.showBlockedTemplateDialog();
            }
            return false;
        }

        for (const [newId, itemId] of Object.entries(newId2ItemIdMap)) {
            Id2UpdatedItem[newId].id = itemId;
        }
        return Id2UpdatedItem;
    }

    async getRadioSetInfo(sign_item_ids) {
        const info = await this.orm.call("sign.template", "get_radio_set_info_by_item_id", [
            this.props.signTemplate.id,
            sign_item_ids,
        ])
        return info;
    }

    prepareTemplateData() {
        const updatedSignItems = {};
        const Id2UpdatedItem = {};
        const items = this.props.iframe?.signItems ?? {};
        for (const page in items) {
            for (const id in items[page]) {
                const signItem = items[page][id].data;
                if (signItem.updated) {
                    Id2UpdatedItem[id] = signItem;
                    const responsible = signItem.responsible;
                    updatedSignItems[id] = {
                        type_id: signItem.type_id[0],
                        required: signItem.required,
                        constant: signItem.constant,
                        name: signItem.placeholder || signItem.name,
                        alignment: signItem.alignment,
                        option_ids: signItem.option_ids,
                        responsible_id: responsible,
                        page: page,
                        posX: signItem.posX,
                        posY: signItem.posY,
                        width: signItem.width,
                        height: signItem.height,
                        radio_set_id: signItem.radio_set_id,
                        document_id: signItem.document_id,
                    };

                    if (id < 0) {
                        updatedSignItems[id]["transaction_id"] = id;
                    }
                }
            }
        }
        return [updatedSignItems, Id2UpdatedItem];
    }

    async rotatePDF() {
        const result = await this.orm.call("sign.template", "rotate_pdf", [
            this.props.signTemplate.id,
        ]);
        if (!result) {
            this.showBlockedTemplateDialog();
        }

        return result;
    }

    showBlockedTemplateDialog() {
        this.dialog.add(AlertDialog, {
            confirm: () => {
                this.props.goBackToKanban();
            },
            body: _t("Somebody is already filling a document which uses this template"),
        });
    }
}
