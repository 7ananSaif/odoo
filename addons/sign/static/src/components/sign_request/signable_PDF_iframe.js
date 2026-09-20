import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { PDFIframe } from "./PDF_iframe";
import { startSignItemNavigator } from "./sign_item_navigator";
import {
    SignNameAndSignatureDialog,
} from "@sign/dialogs/dialogs";

export class SignablePDFIframe extends PDFIframe {
    /**
     * Renders custom elements inside the PDF.js iframe when signing
     * @param {HTMLIFrameElement} iframe
     * @param {Document} root
     * @param {Object} env
     * @param {Object} owlServices
     * @param {Object} props
     */
    constructor(root, env, owlServices, props) {
        super(root, env, owlServices, props);
        this.currentRole = this.props.currentRole;
        this.currentRoleName = this.props.currentName;
        this.signerName = props.signerName;
        this.frameHash =
            (this.props.frameHash && this.props.frameHash.substring(0, 10) + "...") || "";

        this.radioSets = {};
        this.props.signItems.forEach((item) => {
            if(item.radio_set_id) {
                if (item.radio_set_id in this.radioSets) {
                    this.radioSets[item.radio_set_id].items.push(item);
                } else {
                    this.radioSets[item.radio_set_id] = {
                        selected: null,
                        items: [item],
                    }
                }
            }
        })

        for (const radio_set_id in this.radioSets) {
            this.radioSets[radio_set_id].items = this.radioSets[radio_set_id].items.sort((a, b) => {
                return (
                    100 * (a.page - b.page) +
                    10 * (a.posY - b.posY) +
                    (a.posX - b.posX)
                );
            });
        }
    }

    getSignItemById(id) {
        for (const page in this.signItems) {
            if (this.signItems[page].hasOwnProperty(id)) {
                return this.signItems[page][id];
            }
        }
        return undefined;
    }

    /**
     * Modify the selected sign item of the corresponding radio set.
     * @param {SignItem} signItem
     */
    handleRadioItemSelected(signItem) {
        const radio_set_id = signItem.data.radio_set_id;
        if (this.radioSets[radio_set_id].selected !== signItem.data.id) {
            this.radioSets[signItem.data.radio_set_id].selected = signItem.data.id;
        }else if (!signItem.data.required) {
            signItem.el.checked = false;
            this.radioSets[radio_set_id].selected = undefined;
        }
    }

    enableCustom(signItem) {
        if (this.readonly || signItem.data.responsible !== this.currentRole) {
            return;
        }
        const signItemElement = signItem.el;
        const signItemData = signItem.data;
        const signItemType = this.signItemTypesById[signItemData.type_id];
        const { name, item_type: type, auto_value: autoValue } = signItemType;
        if (name === _t("Date")) {
            signItemElement.addEventListener("focus", (e) => {
                this.fillTextSignItem(e.currentTarget, this.signInfo.get('todayFormattedDate'));
            });
        } else if (type === "signature" || type === "initial") {
            signItemElement.addEventListener("click", (e) => {
                this.handleSignatureDialogClick(e.currentTarget, signItemType);
            });
        } else if (type === "radio") {
            signItemElement.addEventListener("click", (e) => {
                this.handleRadioItemSelected(signItem);
            })
        }

        if (autoValue && ["stamp"].includes(type) && this.props.isSignerHasCompany) {
            this.fillStampSignItem(signItemElement, autoValue);
        }

        if (autoValue && ["text", "textarea"].includes(type)) {
            signItemElement.addEventListener("focus", (e) => {
                this.fillTextSignItem(e.currentTarget, autoValue);
            });
        }

        if (type === "selection") {
            if (signItemElement.value) {
                this.handleInput();
            }
            const optionDiv = signItemElement.querySelector(".o_sign_select_options_display");
            const selectElement = optionDiv.querySelector("#selection");

            // Add an event listener to handle the selection change.
            selectElement.addEventListener("change", (e) => {
                const selectedOption = selectElement.options[selectElement.selectedIndex];
                // Extract the data-id from the selected option.
                const selectedValue = selectedOption.dataset.id;
                // Update the value in the signItemElement.
                signItemElement.value = selectedValue;

                // Iterate through all options to update their classes.
                [...selectElement.options].forEach((option) => {
                    if (option.dataset.id === selectedValue) {
                        option.classList.add("o_sign_selected_option");
                        option.classList.remove("o_sign_not_selected_option");
                    } else {
                        option.classList.add("o_sign_not_selected_option");
                        option.classList.remove("o_sign_selected_option");
                    }
                });
                // Call the input handler function.
                this.handleInput();
            });
        }

        if (type == "strikethrough") {
            if (signItemElement.value) {
                this.handleInput();
            }
            if(!signItemData.constant) {
                signItemElement.addEventListener("click", (event) => {
                    if (signItemElement.firstChild.classList.contains("o_sign_strikethrough_line_striked")) {
                        signItemElement.firstChild.classList.remove("o_sign_strikethrough_line_striked");
                        signItemElement.value = "non-striked";
                    } else {
                        signItemElement.firstChild.classList.add("o_sign_strikethrough_line_striked");
                        signItemElement.value = "striked";
                    }
                });
            } else {
                signItemElement.firstChild.classList.add("o_sign_strikethrough_line_striked");
                signItemElement.value = "striked";
            }
        }

        signItemElement.addEventListener("input", this.handleInput.bind(this));
    }

    handleInput() {
        this.checkSignItemsCompletion();
        if(this.props.isDocumentUnsigned()) {
            this.navigator.setTip(_t("next"));
        }
    }

    /**
     * Logic for wizard/mark behavior is:
     * If auto_value is defined and the item is not marked yet, auto_value is used
     * Else, wizard is opened.
     * @param { HTMLElement } signatureItem
     * @param { Object } type
     */
    handleSignatureDialogClick(signatureItem, signItemType) {
        this.refreshSignItems();
        const signature = signatureItem.dataset.signature;
        const { auto_value: autoValue, frame_value: frameValue, item_type: type } = signItemType;
        if (autoValue && !signature) {
            Promise.all([
                this.adjustSignatureSize(autoValue, signatureItem),
                this.adjustSignatureSize(frameValue, signatureItem),
            ]).then(([data, frameData]) => {
                this.fillItemWithSignature(signatureItem, data, { frame: frameData, hash: "0" });
                this.handleInput();
            });
        } else if (type === "initial" && this.nextInitial && !signature) {
            this.adjustSignatureSize(this.nextInitial, signatureItem).then((data) => {
                this.fillItemWithSignature(signatureItem, data);
                this.handleInput();
            });
        } else {
            this.openSignatureDialog(signatureItem, signItemType);
        }
    }

    fillTextSignItem(signItemElement, value) {
        if (signItemElement.value === "") {
            signItemElement.value = value;
            this.handleInput();
        }
    }

    fillStampSignItem(signItemElement, value) {
        if (signItemElement.value === "") {
            signItemElement.value = value;
        }
    }

    closeDialog() {
        this.closeFn && this.closeFn();
        this.closeFn = false;
    }

    updateSignerName(name) {
        this.signerName = name;
    }

    /**
     * Opens the signature dialog
     * @param { HTMLElement } signatureItem
     * @param {*} type
     */
    openSignatureDialog(signatureItem, type) {
        if (this.dialogOpen) {
            return;
        }
        const signature = {
            name: this.signerName || "",
        };
        const frame = {};
        const { height, width } = signatureItem.getBoundingClientRect();
        const signFrame = signatureItem.querySelector(".o_sign_frame");
        this.dialogOpen = true;
        // If we already have an image, we propagate it to populate the "draw" tab
        const signatureImage = signatureItem?.dataset?.signature;
        this.closeFn = this.dialog.add(
            SignNameAndSignatureDialog,
            {
                frame,
                signature,
                signatureType: type.item_type,
                displaySignatureRatio: width / height,
                activeFrame: Boolean(signFrame) || !type.auto_value,
                mode: "auto",
                defaultFrame: type.frame_value || "",
                hash: this.frameHash,
                signatureImage,
                onConfirm: async () => {
                    if (!signature.isSignatureEmpty && signature.signatureChanged) {
                        const signatureName = signature.name;
                        this.props.updateSignerName(signatureName);
                        await frame.updateFrame();
                        const frameData = frame.getFrameImageSrc();
                        const signatureSrc = signature.getSignatureImage();
                        type.auto_value = signatureSrc;
                        type.frame_value = frameData;
                        if (user.userId) {
                            await this.updateUserSignature(type);
                        }
                        this.fillItemWithSignature(signatureItem, signatureSrc, {
                            frame: frameData,
                            hash: this.frameHash,
                        });
                    } else if (signature.signatureChanged) {
                        // resets the sign item
                        delete signatureItem.dataset.signature;
                        delete signatureItem.dataset.frame;
                        signatureItem.replaceChildren();
                        const signHelperSpan = document.createElement("span");
                        signHelperSpan.classList.add("o_sign_helper");
                        signatureItem.append(signHelperSpan);
                        if (type.placeholder) {
                            const placeholderSpan = document.createElement("span");
                            placeholderSpan.classList.add("o_placeholder");
                            placeholderSpan.innerText = type.placeholder;
                            signatureItem.append(placeholderSpan);
                        }
                    }
                    this.closeDialog();
                    this.handleInput();
                },
                onConfirmAll: async () => {
                    const signatureName = signature.name;
                    this.props.updateSignerName(signatureName);
                    await frame.updateFrame();
                    const frameData = frame.getFrameImageSrc();
                    const signatureSrc = signature.getSignatureImage();
                    type.auto_value = signatureSrc;
                    type.frame_value = frameData;
                    if (user.userId) {
                        await this.updateUserSignature(type);
                    }
                    for (const page in this.signItems) {
                        await Promise.all(
                            Object.values(this.signItems[page]).reduce((promiseList, signItem) => {
                                if (
                                    signItem.data.responsible === this.currentRole &&
                                    signItem.data.type_id === type.id
                                ) {
                                    promiseList.push(
                                        Promise.all([
                                            this.adjustSignatureSize(signatureSrc, signItem.el),
                                            this.adjustSignatureSize(frameData, signItem.el),
                                        ]).then(([data, frameData]) => {
                                            this.fillItemWithSignature(signItem.el, data, {
                                                frame: frameData,
                                                hash: this.frameHash,
                                            });
                                        })
                                    );
                                }
                                return promiseList;
                            }, [])
                        );
                    }
                    this.closeDialog();
                    this.handleInput();
                },
            },
            {
                onClose: () => {
                    this.dialogOpen = false;
                },
            }
        );
    }

    checkSignItemsCompletion() {
        this.refreshSignItems();
        const itemsToSign = [];
        for (const page in this.signItems) {
            Object.values(this.signItems[page]).forEach((signItem) => {
                if (
                    !signItem.data.constant &&
                    signItem.data.required &&
                    signItem.data.responsible === this.currentRole &&
                    !signItem.data.value
                ) {
                    if(signItem.data.type === "radio" && this.radioSets[signItem.data.radio_set_id].selected){
                        return;
                    }
                    const el =
                        signItem.data.isEditMode && signItem.el.type === "text"
                            ? el.querySelector("input")
                            : signItem.el;
                    const uncheckedBox = el.value === "on" && !el.checked;
                    if (!((el.value && el.value.trim()) || el.dataset.signature) || uncheckedBox) {
                        itemsToSign.push(signItem);
                    }
                }
            });
        }

         // Updates the set of unsigned documents if is fully signed or any item gets unsigned
        const documentsWithUnsignedItems = this.props.getDocumentsWithUnsignedItems();
        if(itemsToSign.length=== 0) {
            this.props.updateDocumentsWithUnsignedItems(this.props.documentId, false);
        } else if(!documentsWithUnsignedItems.has(this.props.documentId)) {
            this.props.updateDocumentsWithUnsignedItems(this.props.documentId, true);
        }

        return itemsToSign;
    }

    /**
     * Updates the user's signature in the res.user model
     * @param { Object } type
     */
    updateUserSignature(type) {
        return rpc("/sign/update_user_signature", {
            sign_request_id: this.props.requestID,
            role: this.currentRole,
            signature_type: type.item_type === "signature" ? "sign_signature" : "sign_initials",
            datas: type.auto_value,
            frame_datas: type.frame_value,
        });
    }

    /**
     * Extends the rendering context of the sign item based on its data
     * @param {SignItem.data} signItem
     * @returns {Object}
     */
    getContext(signItem) {
        const context = super.getContext(signItem);
        const type = this.signItemTypesById[signItem.type_id];
        if (type.name === _t("Date") && signItem.responsible === this.currentRole) {
            context.placeholder = this.signInfo.get('dateFormat')?.toUpperCase();
        }
        return context;
    }

    /**
     * Hook executed before rendering the sign items and the sidebar
     */
    preRender() {
        super.preRender();
    }

    postRender() {
        super.postRender();
        if (this.props.showThankYouDialog) {
            this.props.openThankYouDialog();
        }
        if (this.readonly) {
            return;
        }
        this.navigator = startSignItemNavigator(
            this,
            this.root.querySelector("#viewerContainer"),
            this.signItemTypesById,
            this.env,
        );
        this.navigator.toggle(this.props.signItems.length > 0);
        this.checkSignItemsCompletion();

        this.root.querySelector("#viewerContainer").addEventListener("scroll", () => {
            if (!this.navigator.state.isScrolling && this.navigator.state.started) {
                if(this.props.isDocumentUnsigned()) {
                    this.navigator.setTip(_t("next"));
                }
            }
        });

        this.root.querySelector("#viewerContainer").addEventListener("keydown", (e) => {
            if (e.key !== "Enter" || (e.target.tagName.toLowerCase() === 'textarea')) {
                return;
            }
            this.navigator.goToNextSignItem();
        });
    }

    signDocument() {
        this.props.signDocuments();
    }

    async _signDocument() {
    }

    /**
     * Gets the signature values from the sign items
     * Gets the frame values
     * @returns { Array } [signature values, frame values, added sign items]
     */
    getSignatureValuesFromConfiguration() {
        const signatureValues = {};
        const frameValues = {};
        const newSignItems = {};
        for (const page in this.signItems) {
            for (const item of Object.values(this.signItems[page])) {
                const responsible = item.data.responsible || 0;
                if (responsible > 0 && responsible !== this.currentRole) {
                    continue;
                }

                const value = this.getSignatureValueFromElement(item);
                const [frameValue, frameHash] = item.el.dataset.signature
                    ? [item.el.dataset.frame, item.el.dataset.frameHash]
                    : [false, false];

                if (!value) {
                    if (item.data.required) {
                        return [{}, {}];
                    }
                    continue;
                }

                signatureValues[item.data.id] = value;
                frameValues[item.data.id] = { frameValue, frameHash };
                if (item.data.isSignItemEditable) {
                    newSignItems[item.data.id] = {
                        type_id: item.data.type_id,
                        required: item.data.required,
                        constant: item.data.constant,
                        name: item.data.name || false,
                        option_ids: item.data.option_ids,
                        responsible_id: responsible,
                        page: page,
                        posX: item.data.posX,
                        posY: item.data.posY,
                        width: item.data.width,
                        height: item.data.height,
                    };
                }
            }
        }

        return [signatureValues, frameValues];
    }

    getSignatureValueFromElement(item) {
        let textArea = item.el.textContent;
        if (!item.data.constant) {
            // remove line breaks, it may update the item value, we can't use it on constant items
            // Moreover, item.el.value is empty for constant items.
            textArea = this.textareaApplyLineBreak(item.el);
        }
        const types = {
            text: () => {
                const textValue =
                    item.el.textContent && item.el.textContent.trim() ? item.el.textContent : false;
                const value =
                    item.el.value && item.el.value.trim()
                        ? item.el.value
                        : item.el.querySelector("input")?.value || false;
                return value || textValue;
            },
            initial: () => item.el.dataset.signature,
            signature: () => item.el.dataset.signature,
            textarea: () => textArea,
            selection: () => (item.el.value && item.el.value.trim() ? item.el.value : false),
            checkbox: () => {
                if (item.el.checked) {
                    return "on";
                } else {
                    return item.data.required ? false : "off";
                }
            },
            radio: () => {
                if(item.el.checked) {
                    return "on";
                } else {
                    return "off";
                }
            },
            strikethrough: () => {
                return item.el.value;
            },
        };
        const type = item.data.type;
        return type in types ? types[type]() : types["text"]();
    }

    textareaApplyLineBreak(element) {
        // Removing wrap in order to have scrollWidth > width
        element.setAttribute("wrap", "off");

        const strRawValue = element.value || element.textContent;
        element.value = "";
        if (!strRawValue) {
           return element.value;
        }
        const nEmptyWidth = element.scrollWidth;
        let nLastWrappingIndex = -1;

        // Computing new lines
        strRawValue.split("").forEach((curChar, i) => {
            element.value += curChar;

            if (curChar === " " || curChar === "-" || curChar === "+") {
                nLastWrappingIndex = i;
            }

            if (element.scrollWidth > nEmptyWidth) {
                let buffer = "";
                if (nLastWrappingIndex >= 0) {
                    for (let j = nLastWrappingIndex + 1; j < i; j++) {
                        buffer += strRawValue.charAt(j);
                    }
                    nLastWrappingIndex = -1;
                }
                buffer += curChar;
                element.value = element.value.substr(0, element.value.length - buffer.length);
                element.value += "\n" + buffer;
            }
        });
        element.setAttribute("wrap", "");
        return element.value;
    }

    disableItems() {
        const items = this.root.querySelectorAll(".o_sign_sign_item");
        for (const item of Array.from(items)) {
            item.classList.add("o_sign_sign_item_pdfview");
        }
    }
}
