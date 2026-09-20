import {
    Component,
    onWillStart,
    onMounted,
    onWillDestroy,
    onWillUnmount,
    reactive,
    useState,
} from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { omit } from "@web/core/utils/objects";
import { useOwnedDialogs, useService } from "@web/core/utils/hooks";

import { Many2ManyTagsField } from "@web/views/fields/many2many_tags/many2many_tags_field";
import { CharField } from "@web/views/fields/char/char_field";
import { Record as _Record } from "@web/model/record";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { BooleanField } from "@web/views/fields/boolean/boolean_field";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

import { ReportEditorSnackbar } from "@web_studio/client_action/report_editor/report_editor_snackbar";
import { useEditorMenuItem } from "@web_studio/client_action/editor/edition_flow";
import { memoizeOnce } from "@web_studio/client_action/utils";
import { ReportEditorIframe } from "../report_editor_iframe";
import { Editor } from "@html_editor/editor";
import { closestElement } from "@html_editor/utils/dom_traversal";
import { ReportRecordNavigation } from "../report_editor_xml/report_record_navigation";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { getReportEditorPlugins } from "./editor_plugins/report_editor_plugin";

class __Record extends _Record.components._Record {
    setup() {
        super.setup();
        const willSaveUrgently = () => this.model.bus.trigger("WILL_SAVE_URGENTLY");
        onMounted(() => {
            this.env.reportEditorModel.bus.addEventListener("WILL_SAVE_URGENTLY", willSaveUrgently);
        });

        onWillDestroy(() =>
            this.env.reportEditorModel.bus.removeEventListener(
                "WILL_SAVE_URGENTLY",
                willSaveUrgently
            )
        );
    }
}

class Record extends _Record {
    static components = { ..._Record.components, _Record: __Record };
}

class UndoRedo extends Component {
    static template = "web_studio.ReportEditorWysiwyg.UndoRedo";
    static props = {
        state: Object,
        className: { type: String, optional: true },
    };
}

class ResetConfirmationPopup extends ConfirmationDialog {
    static template = "web_studio.ReportEditorWysiwyg.ResetConfirmationPopup";
    static props = {
        ...omit(ConfirmationDialog.props, "body"),
        state: Object,
    };
}

export class ReportEditorWysiwyg extends Component {
    static components = {
        CharField,
        Record,
        Many2ManyTagsField,
        Many2OneField,
        BooleanField,
        UndoRedo,
        ReportEditorIframe,
        ReportRecordNavigation,
        CheckBox,
    };
    static props = {
        paperFormatStyle: String,
    };
    static template = "web_studio.ReportEditorWysiwyg";

    setup() {
        this.action = useService("action");
        this.addDialog = useOwnedDialogs();
        this.notification = useService("notification");

        this._getReportQweb = memoizeOnce(() => {
            const tree = new DOMParser().parseFromString(
                this.reportEditorModel.reportQweb,
                "text/html"
            );
            const htmlNode = tree.firstElementChild;
            htmlNode.translate = false;
            return htmlNode;
        });

        const reportEditorModel = (this.reportEditorModel = useState(this.env.reportEditorModel));
        this.reportRecordHooks = {
            onRecordChanged: (rec) => (this.reportEditorModel.reportData = rec.data),
        };

        useEditorMenuItem({
            component: ReportEditorSnackbar,
            props: {
                state: reportEditorModel,
                onSave: this.save.bind(this),
                onDiscard: this.discard.bind(this),
            },
        });

        // This little reactive is to be bound to the editor, so we create it here.
        // This could have been a useState, but the current component doesn't use it.
        // Instead, it passes it to a child of his,
        this.undoRedoState = reactive({
            canUndo: false,
            canRedo: false,
            undo: () => this.editor?.shared.history.undo(),
            redo: () => this.editor?.shared.history.redo(),
        });

        onWillStart(() => this.reportEditorModel.loadReportQweb());

        onWillUnmount(() => {
            this.reportEditorModel.bus.trigger("WILL_SAVE_URGENTLY");
            this.save({ urgent: true });
            if (this.editor) {
                this.editor.destroy(true);
            }
        });
    }

    instantiateEditor({ editable } = {}) {
        this.undoRedoState.canUndo = false;
        this.undoRedoState.canRedo = false;
        const onEditorChange = () => {
            const canUndo = this.editor.shared.history.canUndo();
            this.reportEditorModel.isDirty = canUndo;
            Object.assign(this.undoRedoState, {
                canUndo: canUndo,
                canRedo: this.editor.shared.history.canRedo(),
            });
        };

        editable.querySelectorAll("[ws-view-id]").forEach((el) => {
            el.setAttribute("contenteditable", "true");
        });
        const editor = new Editor(
            {
                Plugins: getReportEditorPlugins(),
                onChange: onEditorChange,
                getRecordInfo: () => {
                    const { anchorNode } = this.editor.shared.selection.getEditableSelection();
                    if (!anchorNode) {
                        return {};
                    }
                    const lastViewParent = closestElement(anchorNode, "[ws-view-id]");
                    if (!lastViewParent) {
                        return {};
                    }
                    return {
                        resModel: "ir.ui.view",
                        resId: parseInt(lastViewParent.getAttribute("ws-view-id")),
                        field: "arch",
                    };
                },
                reportResModel: this.reportEditorModel.reportResModel,
                allowVideo: false,
                allowImageTransform: false,
                allowImageResize: false,
            },
            this.env.services
        );
        editor.attachTo(editable);
        // disable the qweb's plugin class: its style is too complex and confusing
        // in the case of reports
        editable.classList.remove("odoo-editor-qweb");
        return editor;
    }

    onIframeLoaded({ iframeRef }) {
        if (this.editor) {
            this.editor.destroy(true);
            this.editor = null;
        }
        this.iframeRef = iframeRef;
        const doc = iframeRef.el.contentDocument;
        doc.body.classList.remove("container");

        if (odoo.debug) {
            ["t-esc", "t-out", "t-field"].forEach((tAtt) => {
                doc.querySelectorAll(`*[${tAtt}]`).forEach((e) => {
                    // Save the previous title to set it back before saving the report
                    if (e.hasAttribute("title")) {
                        e.setAttribute("data-oe-title", e.getAttribute("title"));
                    }
                    e.setAttribute("title", e.getAttribute(tAtt));
                });
            });
        }
        if (!this.reportEditorModel._errorMessage && !this.reportEditorModel.inPreview) {
            this.editor = this.instantiateEditor({ editable: doc.querySelector("#wrapwrap") });
        }
        this.reportEditorModel.setInEdition(false);
    }

    get reportQweb() {
        const model = this.reportEditorModel;
        return this._getReportQweb(`${model.renderKey}_${model.reportQweb}`).outerHTML;
    }

    get reportRecordProps() {
        const model = this.reportEditorModel;
        return {
            fields: model.reportFields,
            activeFields: model.reportActiveFields,
            values: model.reportData,
        };
    }

    async save({ urgent = false } = {}) {
        if (!this.editor) {
            await this.reportEditorModel.saveReport({ urgent });
            return;
        }
        const htmlParts = {};
        const editable = this.editor.getElContent();

        // Clean technical title
        if (odoo.debug) {
            editable.querySelectorAll("*[t-field],*[t-out],*[t-esc]").forEach((e) => {
                if (e.hasAttribute("data-oe-title")) {
                    e.setAttribute("title", e.getAttribute("data-oe-title"));
                    e.removeAttribute("data-oe-title");
                } else {
                    e.removeAttribute("title");
                }
            });
        }

        editable.querySelectorAll("[ws-view-id].o_dirty").forEach((el) => {
            el.classList.remove("o_dirty");
            el.removeAttribute("contenteditable");
            const viewId = el.getAttribute("ws-view-id");
            if (!viewId) {
                return;
            }
            Array.from(el.querySelectorAll("[t-call]")).forEach((el) => {
                el.removeAttribute("contenteditable");
                el.replaceChildren();
            });

            Array.from(el.querySelectorAll("[oe-origin-t-out]")).forEach((el) => {
                el.replaceChildren();
            });
            if (!el.hasAttribute("oe-origin-class") && el.getAttribute("class") === "") {
                el.removeAttribute("class");
            }

            const callGroupKey = el.getAttribute("ws-call-group-key");
            const type = callGroupKey ? "in_t_call" : "full";

            const escaped_html = el.outerHTML;
            htmlParts[viewId] = htmlParts[viewId] || [];

            htmlParts[viewId].push({
                call_key: el.getAttribute("ws-call-key"),
                call_group_key: callGroupKey,
                type,
                html: escaped_html,
            });
        });
        await this.reportEditorModel.saveReport({ htmlParts, urgent });
    }

    async discard() {
        if (this.editor) {
            const selection = this.editor.document.getSelection();
            if (selection) {
                selection.removeAllRanges();
            }
        }
        this.env.services.dialog.add(ConfirmationDialog, {
            body: _t(
                "If you discard the current edits, all unsaved changes will be lost. You can cancel to return to edit mode."
            ),
            confirm: () => this.reportEditorModel.discardReport(),
            cancel: () => {},
        });
    }

    async resetReport() {
        const state = reactive({ includeHeaderFooter: true });
        this.addDialog(ResetConfirmationPopup, {
            title: _t("Reset report"),
            confirmLabel: _t("Reset report"),
            confirmClass: "btn-danger",
            cancelLabel: _t("Go back"),
            state,
            cancel: () => {},
            confirm: async () => {
                await this.reportEditorModel.saveReport();
                try {
                    await this.reportEditorModel.resetReport(state.includeHeaderFooter);
                } finally {
                    this.reportEditorModel.renderKey++;
                }
            },
        });
    }

    async openReportFormView() {
        await this.save();
        return this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "ir.actions.report",
                res_id: this.reportEditorModel.editedReportId,
                views: [[false, "form"]],
                target: "current",
            },
            { clearBreadcrumbs: true }
        );
    }

    async editSources() {
        await this.save();
        this.reportEditorModel.mode = "xml";
    }

    async togglePreview(toValue) {
        if (toValue) {
            const saved = await this.save();
            if (!saved) {
                await this.reportEditorModel.loadReportHtml();
            }
        }
        this.reportEditorModel.inPreview = toValue;
    }
}
