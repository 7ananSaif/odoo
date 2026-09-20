import { App, Component, xml, whenReady, useEffect, useComponent, useState } from "@odoo/owl";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { useService } from "@web/core/utils/hooks";
import { getTemplate } from "@web/core/templates";
import { makeEnv, startServices } from "@web/env";
import { SignablePDFIframe } from "./signable_PDF_iframe";
import { buildPDFViewerURL, injectPDFCustomStyles } from "@sign/components/sign_request/utils";
import { _t, appTranslateFn } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { hidePDFJSButtons } from "@web/core/utils/pdfjs";
import {
    SignRefusalDialog,
    SignNameAndSignatureDialog,
    ThankYouDialog,
    PublicSignerDialog,
    SMSSignerDialog,
    NextDirectSignDialog,
} from "@sign/dialogs/dialogs";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export function datasetFromElements(elements) {
    return Array.from(elements).map((el) => {
        return Object.entries(el.dataset).reduce((dataset, [key, value]) => {
            try {
                const parsed = JSON.parse(value);
                if (key === "value" && typeof parsed === 'number' && parsed > Number.MAX_SAFE_INTEGER) {
                    // Keep numbers as strings below to avoid MAX_SAFE_INTEGER issues.
                    dataset[key] = value;
                } else {
                    dataset[key] = parsed;
                }
            } catch {
                dataset[key] = value;
            }
            return dataset;
        }, {});
    });
}

export class Document extends Component {
    static template = xml`<t t-slot='default'/>`;
    static props = ["parent", "PDFIframeClass"];

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.ui = useService("ui");
        this.signInfo = useService("signInfo");

        this.state = useState({
            documentsWithUnsignedItems: new Set(),
            viewedDocuments: new Set(),
            openedDocumentIndex: 0,
        });

        useEffect(
            () => {
                this.getDataFromHTML();
                if (!this.requestID) {
                    return;
                }
                this.signInfo.set({
                    documentId: this.requestID,
                    signRequestToken: this.requestToken,
                    signRequestState: this.requestState,
                    signRequestItemId: this.signRequestItemId,
                    signRequestItemToken: this.accessToken,
                    todayFormattedDate: this.todayFormattedDate,
                    dateFormat: this.dateFormat,
                });
            },
            () => []
        );

        useEffect(
            () => {
                if (
                    !this.state.documentsWithUnsignedItems ||
                    !this.state.viewedDocuments ||
                    !this.documents ||
                    this.documents.length === 0
                ) {
                    return;
                }

                const hasUnsignedDocs = this.state.documentsWithUnsignedItems.size > 0;
                const currentDocUnsigned = this.isDocumentUnsigned();
                const allDocsViewed = this.state.viewedDocuments.size === this.documents.length;

                if (!hasUnsignedDocs && allDocsViewed) {
                    // If all documents are signed and viewed, show validation banner
                    this.showBanner(this.validateBanner);
                    return;
                }

                // Hide validation banner since there are unsigned/un-viewed documents
                this.hideBanner(this.validateBanner);

                if (currentDocUnsigned) {
                    // If current document needs signing, hide "next document" banner
                    this.hideBanner(this.nextDocumentBanner);
                } else {
                    // If current document is signed or have nothing to sign, show "next document" banner
                    this.showBanner(this.nextDocumentBanner);
                }
            },
            () => [this.state.documentsWithUnsignedItems, this.state.openedDocumentIndex]
        );
    }

    /**
     * Returns the set of unsigned documents
     * @returns {Set}
     */
    getDocumentsWithUnsignedItems() {
        return this.state.documentsWithUnsignedItems;
    }

    /**
     * Checks if the current document has unsigned items
     * @returns {boolean}
     */
    isDocumentUnsigned(){
        if(!this.documents) return false;
        const documentId = this.documents[this.state.openedDocumentIndex].id;
        return this.state.documentsWithUnsignedItems.has(documentId);
    }

    /**
     * Updates the set of unsigned documents
     * @param {string} documentId
     * @param {boolean} hasUnsignedItems
     */
    updateDocumentsWithUnsignedItems(documentId, hasUnsignedItems) {
        const newSet = new Set(this.state.documentsWithUnsignedItems);
        if (hasUnsignedItems) {
            newSet.add(documentId);
        } else {
            newSet.delete(documentId);
        }
        this.state.documentsWithUnsignedItems = newSet;
        this.controlNavigatorVisibility(hasUnsignedItems);
    }

    documentNavigate(shift) {
        this.state.openedDocumentIndex = (this.state.openedDocumentIndex + shift + this.documents.length) % this.documents.length;
        this.state.viewedDocuments.add(this.documents[this.state.openedDocumentIndex].id);
        this.documents.forEach((doc, index) => {
            if (index === this.state.openedDocumentIndex) {
                doc.iframe.classList.remove("d-none");
            } else {
                doc.iframe.classList.add("d-none");
            }
        });
        document.querySelectorAll(".o_sign_document_navigator_text").forEach((text) => {
            if (text)
                text.textContent = (this.state.openedDocumentIndex + 1) + " / " + this.documents.length;
        });
    }

    showBanner(banner) {
        if (banner) {
            banner.style.display = "block";
            const an = banner.animate(
                { opacity: 1 },
                { duration: 500, fill: "forwards" }
            );
            an.finished.then(() => {
                if (this.env.isSmall) {
                    banner.scrollIntoView({
                        behavior: "smooth",
                        block: "center",
                        inline: "center",
                    });
                }
            });
        }
    }

    hideBanner(banner) {
        if (banner) {
            banner.style.display = "none";
            banner.style.opacity = 0;
        }
    }

    /**
     * Controls the visibility of the navigator to be invisible if current document is signed
     */
    controlNavigatorVisibility(hasUnsignedItems) {
        if (this.documents) {
            const currentDoc = this.documents[this.state.openedDocumentIndex];
            const iframeManager = currentDoc.iframeManager;
            if (iframeManager && iframeManager.navigator) {
                // If hasUnsignedItems is false, we need to check if there are unsigned items for the current role in the document
                if (!hasUnsignedItems && this.isDocumentUnsigned()) {
                    // Check if there are items for the current role
                    hasUnsignedItems = Object.values(iframeManager.signItems || {}).some(pageItems =>
                        Object.values(pageItems).some(item => item.data.responsible === iframeManager.currentRole)
                    );
                }
                iframeManager.navigator.toggle(hasUnsignedItems);
            }
        }
    }

    getDataFromHTML() {
        const { el: parentEl } = this.props.parent;
        this.documents = datasetFromElements(parentEl.querySelectorAll(".o_sign_document_input_info"));
        const iframes = parentEl.querySelectorAll(".o_sign_pdf_iframe");
        for (let i = 0; i < this.documents.length; i++) {
            if (i > 0) {
                iframes[i].classList.add("d-none");
            }
            iframes[i].setAttribute(
                "src",
                buildPDFViewerURL(this.documents[i].attachmentLocation, this.env.isSmall)
            );
            hidePDFJSButtons(iframes[i], {
                hideDownload: true,
                hidePrint: true,
                hidePresentation: true,
                hideRotation: true,
            });
            this.documents[i].iframe = iframes[i];
        }
        this.documents.forEach((document) => {
            document.iframe.addEventListener("load", () => {
                setTimeout(() => {
                    document.iframeManager = this.initializeIframe(document.iframe, document.id);
                }, 1);
            })
        });

        document.querySelectorAll(".o_sign_document_navigator_text").forEach((text) => {
            if (text)
                text.textContent = "1 / " + this.documents.length;
        });
        document.querySelectorAll(".o_sign_document_navigator_left_arrow").forEach((arrow) => {
            arrow?.addEventListener("click", (e) => this.documentNavigate(-1));
        });
        document.querySelectorAll(".o_sign_document_navigator_right_arrow").forEach((arrow) => {
            arrow?.addEventListener("click", (e) => this.documentNavigate(1));
        });

        this.templateName = parentEl.querySelector("#o_sign_input_template_name")?.value;
        this.templateID = parseInt(parentEl.querySelector("#o_sign_input_template_id")?.value);
        this.templateItemsInProgress = parseInt(
            parentEl.querySelector("#o_sign_input_template_in_progress_count")?.value
        );
        this.requestID = parseInt(parentEl.querySelector("#o_sign_input_sign_request_id")?.value);
        this.requestToken = parentEl.querySelector("#o_sign_input_sign_request_token")?.value;
        this.requestState = parentEl.querySelector("#o_sign_input_sign_request_state")?.value;
        this.signRequestItemId = parseInt(parentEl.querySelector("#o_sign_input_sign_request_item_id")?.value);
        this.accessToken = parentEl.querySelector("#o_sign_input_access_token")?.value;
        this.todayFormattedDate = parentEl.querySelector("#o_sign_input_today_formatted_date")?.value;
        this.dateFormat= parentEl.querySelector("#o_sign_input_date_format")?.value;
        this.templateEditable = Boolean(parentEl.querySelector("#o_sign_input_template_editable"));
        this.authMethod = parentEl.querySelector("#o_sign_input_auth_method")?.value;
        this.signerName = parentEl.querySelector("#o_sign_signer_name_input_info")?.value;
        this.signerPhone = parentEl.querySelector("#o_sign_signer_phone_input_info")?.value;
        this.redirectURL = parentEl.querySelector("#o_sign_input_optional_redirect_url")?.value;
        this.redirectURLText = parentEl.querySelector(
            "#o_sign_input_optional_redirect_url"
        )?.value;
        this.redirectURLText = parentEl.querySelector(
            "#o_sign_input_optional_redirect_url_text"
        )?.value;
        this.isSignerHasCompany = Boolean(parentEl.querySelector("#o_sign_input_is_signer_user")?.value);
        this.types = datasetFromElements(
            parentEl.querySelectorAll(".o_sign_field_type_input_info")
        );
        const items = datasetFromElements(parentEl.querySelectorAll(".o_sign_item_input_info"));
        this.documents.forEach((document) => document.items = items.filter(item => item.document_id === document.id));
        this.state.documentsWithUnsignedItems = new Set(
            this.documents
                .filter(doc => doc.items?.length > 0)
                .map(doc => doc.id)
        );
        this.state.viewedDocuments = new Set([this.documents[0].id]);
        this.selectOptions = datasetFromElements(
            parentEl.querySelectorAll(".o_sign_select_options_input_info")
        );
        this.showThankYouDialog = Boolean(parentEl.querySelector("#o_sign_show_thank_you_dialog"));
        this.validateBanner = parentEl.querySelector(".o_sign_validate_banner");
        this.validateButton = parentEl.querySelector(".o_validate_button");
        this.nextDocumentBanner = parentEl.querySelector(".o_sign_next_document_banner");
        this.nextDocumentButton = parentEl.querySelector(".o_next_document_button");
        this.currentRole = parseInt(parentEl.querySelector("#o_sign_input_current_role")?.value);
        this.currentName = parentEl.querySelector("#o_sign_input_current_role_name")?.value;

        this.isUnknownPublicUser = Boolean(parentEl.querySelector("#o_sign_is_public_user"));
        this.frameHash = parentEl.querySelector("#o_sign_input_sign_frame_hash")?.value;
        this.validateButton?.addEventListener("click", () => {
            this.signDocuments();
        });
        this.nextDocumentButton?.addEventListener("click", () => {
            this.documentNavigate(1);
        });
    }

    initializeIframe(iframe, sign_document_id) {
        if (!iframe.contentDocument.querySelector('link[href*="pdfjs_overrides.css"]')) {
            injectPDFCustomStyles(iframe.contentDocument);
        }
        const props = this.getIframeProps(sign_document_id);
        const iframeManager = new this.props.PDFIframeClass(
            iframe.contentDocument,
            this.env,
            {
                rpc,
                orm: this.orm,
                dialog: this.dialog,
                ui: this.ui,
                signInfo: this.signInfo,
            },
            props,
        );
        return iframeManager;
    }

    // **** Signing ****
    getMailFromSignItems() {
        let mail = "";
        for (let i = 0; i < this.documents.length; i++) {
            const document = this.documents[i];
            const iframeManager = document.iframeManager;
            for (const page in iframeManager.signItems) {
                Object.values(iframeManager.signItems[page]).forEach(({ el }) => {
                    const childInput = el.querySelector("input");
                    const value = el.value || (childInput && childInput.value);
                    if (value && value.indexOf("@") >= 0) {
                        mail = value;
                    }
                });
            }
        }
        return mail;
    }

    updateSignerName(name) {
        this.signerName = name;
        this.documents.forEach((document) => document.iframeManager.updateSignerName(name));
    }

    async openAuthDialog() {
        const authDialog = await this.getAuthDialog();
        if (authDialog.component) {
            this.closeFn = this.dialog.add(authDialog.component, authDialog.props, {
                onClose: () => {
                    this.validateButton.removeAttribute("disabled");
                },
            });
        } else {
            this._sign();
        }
    }

    async getAuthDialog() {
        if (this.authMethod === "sms" && !this.signatureInfo.smsToken) {
            const credits = await rpc("/sign/has_sms_credits");
            if (credits) {
                return {
                    component: SMSSignerDialog,
                    props: {
                        signerPhone: this.signerPhone,
                        postValidation: (code) => {
                            this.signatureInfo.smsToken = code;
                            return this._signDocuments();
                        },
                    },
                };
            }
            return false;
        }
        return false;
    }

    closeDialog() {
        this.closeFn && this.closeFn();
        this.closeFn = false;
    }

    async signDocuments() {
        this.validateBanner.setAttribute("disabled", true);
        this.signatureInfo = {
            name: this.signerName || "",
            mail: this.getMailFromSignItems(),
            signatureValues: {},
            frameValues: {},
        };
        for (let i = 0; i < this.documents.length; i++) {
            const iframeManager = this.documents[i].iframeManager;
            const [signatureValues, frameValues] = iframeManager.getSignatureValuesFromConfiguration();
            Object.assign(this.signatureInfo.signatureValues, signatureValues);
            Object.assign(this.signatureInfo.frameValues, frameValues);
        }
        const noSignItems = this.documents.every((document) => {
            const iframeManager = document.iframeManager;
            return Object.keys(iframeManager.signItems).length === 0;
        });
        this.signatureInfo.hasNoSignature =
            Object.keys(this.signatureInfo.signatureValues).length === 0 && noSignItems;
        this._signDocuments();
    }

    _signDocuments(){
        this.validateButton.setAttribute("disabled", true);
        if (this.signatureInfo.hasNoSignature) {
            const signature = {
                name: this.signerName || "",
            };
            this.closeFn = this.dialog.add(SignNameAndSignatureDialog, {
                signature,
                onConfirm: () => {
                    this.signatureInfo.name = signature.name;
                    this.signatureInfo.signatureValues = signature
                        .getSignatureImage()
                        .split(",")[1];
                    this.signatureInfo.frameValues = [];
                    this.signatureInfo.hasNoSignature = false;
                    this.closeDialog();
                    this._signDocuments();
                },
            });
        } else if (this.isUnknownPublicUser) {
            this.closeFn = this.dialog.add(
                PublicSignerDialog,
                {
                    name: this.signatureInfo.name,
                    mail: this.signatureInfo.mail,
                    postValidation: async (requestID, requestToken, accessToken) => {
                        this.signInfo.set({
                            documentId: requestID,
                            signRequestToken: requestToken,
                            signRequestItemToken: accessToken,
                        });
                        this.requestID = requestID;
                        this.requestToken = requestToken;
                        this.accessToken = accessToken;
                        if (this.coords) {
                            await rpc(
                                `/sign/save_location/${requestID}/${accessToken}`,
                                this.coords
                            );
                        }
                        this.isUnknownPublicUser = false;
                        this._signDocuments();
                    },
                },
                {
                    onClose: () => {
                        this.validateButton.removeAttribute("disabled");
                    },
                }
            );
        } else if (this.authMethod) {
            this.openAuthDialog();
        } else {
            this._sign();
        }
    }

    _getRouteAndParams() {
        const route = this.signatureInfo.smsToken
            ? `/sign/sign/${encodeURIComponent(this.requestID)}/${encodeURIComponent(
                  this.accessToken
              )}/${encodeURIComponent(this.signatureInfo.smsToken)}`
            : `/sign/sign/${encodeURIComponent(this.requestID)}/${encodeURIComponent(
                  this.accessToken
              )}`;

        const params = {
            signature: this.signatureInfo.signatureValues,
            frame: this.signatureInfo.frameValues,
        };

        return [route, params];
    }

    disableItems() {
        for (let i = 0; i < this.documents.length; i++) {
            const iframeManager = this.documents[i].iframeManager;
            iframeManager.disableItems();
        }
    }

    openThankYouDialog() {
        this.dialog.add(ThankYouDialog, {
            redirectURL: this.redirectURL,
            redirectURLText: this.redirectURLText,
        });
    }

    async _sign() {
        const [route, params] = this._getRouteAndParams();
        this.ui.block();
        const response = await rpc(route, params).finally(() => this.ui.unblock());
        this.validateButton.removeAttribute("disabled");
        if (response.success) {
            this.signInfo.set({companyCountryCode: response.company_country_code});
            if (response.url) {
                document.location.pathname = response.url;
            } else {
                this.disableItems();
                // only available in backend
                const nameList = this.signInfo.get("nameList");
                if (nameList && nameList.length > 0) {
                    this.dialog.add(NextDirectSignDialog);
                } else {
                    this.openThankYouDialog();
                }
            }
        } else {
            if (response.sms) {
                this.dialog.add(AlertDialog, {
                    title: _t("Error"),
                    body: _t(
                        "Your signature was not submitted. Ensure the SMS validation code is correct."
                    ),
                });
            } else {
                this.dialog.add(
                    AlertDialog,
                    {
                        title: _t("Error"),
                        body: _t(
                            "Sorry, an error occurred, please try to fill the document again."
                        ),
                    },
                    {
                        onClose: () => {
                            window.location.reload();
                        },
                    }
                );
            }
            this.validateButton.setAttribute("disabled", true);
        }
    }

    getIframeProps(sign_document_id) {
        const document = this.documents.find((document) => document.id === sign_document_id);
        return {
            attachmentLocation: document.attachmentLocation,
            requestID: this.requestID,
            requestToken: this.requestToken,
            accessToken: this.accessToken,
            signItemTypes: this.types,
            signItems: document.items,
            hasSignRequests: false,
            signItemOptions: this.selectOptions,
            currentRole: this.currentRole,
            currentName: this.currentName,
            readonly: document.iframe.getAttribute("readonly") === "readonly",
            frameHash: this.frameHash,
            signerName: this.signerName,
            signerPhone: this.signerPhone,
            isUnknownPublicUser: this.isUnknownPublicUser,
            authMethod: this.authMethod,
            redirectURL: this.redirectURL,
            redirectURLText: this.redirectURLText,
            templateEditable: this.templateEditable,
            showThankYouDialog: this.showThankYouDialog,
            isSignerHasCompany: this.isSignerHasCompany,
            openThankYouDialog: () => this.openThankYouDialog(),
            documentId: sign_document_id,
            updateDocumentsWithUnsignedItems: (documentId, hasUnsignedItems) =>
                this.updateDocumentsWithUnsignedItems(documentId, hasUnsignedItems),
            isDocumentUnsigned: () => this.isDocumentUnsigned(),
            getDocumentsWithUnsignedItems: () => this.getDocumentsWithUnsignedItems(),
            signDocuments: () => this.signDocuments(),
            updateSignerName: (name) => this.updateSignerName(name),
        };
    }
}

function usePublicRefuseButton() {
    const component = useComponent();
    useEffect(
        () => {
            const refuseButtons = document.querySelectorAll(".o_sign_refuse_document_button");
            if (refuseButtons) {
                refuseButtons.forEach((button) =>
                    button.addEventListener("click", () => {
                        component.dialog.add(SignRefusalDialog);
                    })
                );
                if (new URLSearchParams(window.location.search).get("refuse_document") === "1") {
                    refuseButtons[0].click();
                }
            }
        },
        () => []
    );
}

export class SignableDocument extends Document {
    static components = {
        MainComponentsContainer,
    };
    static template = xml`<MainComponentsContainer/>`;

    setup() {
        super.setup();
        this.coords = {};
        usePublicRefuseButton();
        useEffect(
            () => {
                if (this.requestID) {
                    // Geolocation
                    const { el: parentEl } = this.props.parent;
                    const askLocation = parentEl.getElementById(
                        "o_sign_ask_location_input"
                    );
                    if (askLocation && navigator.geolocation) {
                        navigator.geolocation.getCurrentPosition(
                            ({ coords: { latitude, longitude } }) => {
                                Object.assign(this.coords, {
                                    latitude,
                                    longitude,
                                });
                                if (this.requestState !== "shared") {
                                    rpc(
                                        `/sign/save_location/${this.requestID}/${this.accessToken}`,
                                        this.coords
                                    );
                                }
                            }
                        , () => {}, {enableHighAccuracy: true}
                        );
                    }
                }
            },
            () => [this.requestID]
        );
    }

    getIframeProps(sign_document_id) {
        return {
            ...super.getIframeProps(sign_document_id),
            coords: this.coords,
        };
    }
}

/**
 * Mounts the SignableComponent
 * @param { HTMLElement } parent
 */
export async function initDocumentToSign(parent) {
    // Manually add 'sign' to module list and load the translations
    const env = makeEnv();
    await startServices(env);
    await whenReady();
    const app = new App(SignableDocument, {
        name: "Signable Document",
        env,
        props: {
            parent: {el: parent},
            PDFIframeClass: SignablePDFIframe },
        getTemplate,
        dev: env.debug,
        translatableAttributes: ["data-tooltip"],
        translateFn: appTranslateFn,
    });
    await app.mount(parent.body);
}
