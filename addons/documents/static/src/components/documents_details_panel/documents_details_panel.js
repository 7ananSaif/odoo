import { _t } from "@web/core/l10n/translation";
import { ModelSelector } from "@web/core/model_selector/model_selector";
import { user } from "@web/core/user";
import { memoize } from "@web/core/utils/functions";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";
import { CharField } from "@web/views/fields/char/char_field";
import { Many2OneAvatarField } from "@web/views/fields/many2one_avatar/many2one_avatar_field";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

import { DocumentsDetailsMany2ManyTagsField } from "@documents/views/fields/documents_details_many2many_tags/documents_details_many2many_tags_field";
import { DocumentsDetailsMany2OneField } from "@documents/views/fields/documents_details_many2one/documents_details_many2one_field";
import { DocumentsTypeIcon } from "@documents/views/fields/documents_type_icon/documents_type_icon";

import { Component, onWillRender, onWillUpdateProps, reactive, useState } from "@odoo/owl";

// Small hack, memoize uses the first argument as cache key, but we need the orm which will not be the same.
const getDetailsPanelResModels = memoize((_null, orm) =>
    orm.call("documents.document", "get_details_panel_res_models")
);

export class DocumentsDetailsPanel extends Component {
    static components = {
        CharField,
        DocumentsDetailsMany2ManyTagsField,
        DocumentsDetailsMany2OneField,
        DocumentsTypeIcon,
        Many2OneAvatarField,
        Many2OneField,
        ModelSelector,
    };
    static props = {
        record: { type: Object, optional: true },
        nbViewItems: { type: Number, optional: true },
    };
    static template = "documents.DocumentsDetailsPanel";

    setup() {
        this.action = useService("action");
        /** @type {import("@documents/core/document_service").DocumentService} */
        this.documentService = useService("document.document");
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        onWillRender(() => {
            this.record = new Proxy(reactive(this.props.record), isDetailsPanelRecordHandler);
        });

        // Use a state for the model to not write on the record the model without record id
        this.state = useState({
            resModel: this.props.record.data.res_model,
            resModelName: this.props.record.data.res_model_name || "",
            models: [],
        });
        getDetailsPanelResModels(null, this.orm).then((models) => (this.state.models = models));
        onWillUpdateProps((nextProps) => {
            this.state.resModel = nextProps.record.data.res_model;
            this.state.resModelName = nextProps.record.data.res_model_name || "";
        });
    }

    async openLinkedRecord() {
        const { res_model, res_id } = this.record.data || {};
        if (!res_id?.resId || !res_model) {
            return;
        }
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_id: res_id.resId,
            res_model,
            views: [[false, "form"]],
            target: "current",
        });
    }

    get userPermissionViewOnly() {
        return (
            !!this.record.data?.lock_uid ||
            this.record.data?.user_permission !== "edit" ||
            (!this.documentService.userIsDocumentManager &&
                this.record.data?.user_folder_id === "COMPANY")
        );
    }

    get fileSize() {
        if (this.record.data?.type !== "folder" || this.props.record.isContainer) {
            const nBytes = this.record.data.file_size || 0;
            if (nBytes) {
                return `${this.record.isContainer ? "~" : ""}${formatFloat(nBytes, {
                    humanReadable: true,
                })}B`;
            }
        }
        return "";
    }

    get rootFolderPlaceholder() {
        return {
            MY: _t("My Drive"),
            COMPANY: _t("Company"),
            SHARED: _t("Shared with me"),
        }[this.props.record.data?.user_folder_id];
    }

    get activeCompanies() {
        return user.activeCompanies.map((c) => c.id);
    }

    async onModelSelected(value) {
        this.state.resModel = value.technical;
        this.state.resModelName = value.label || "";
        await this.props.record.update({ res_id: false, res_model: false }, { save: true });
        if (this.state.resModel) {
            this.dialog.add(
                SelectCreateDialog,
                {
                    title: _t("Select a Record To Link"),
                    noCreate: true,
                    multiSelect: false,
                    resModel: this.state.resModel,
                    onSelected: async (resIds) => {
                        if (resIds.length) {
                            await this.onResIdUpdate(resIds);
                        }
                    },
                },
                {
                    onClose: () => {
                        if (!this.record.data.res_id) {
                            this.onRecordReset();
                        }
                    },
                }
            );
        }
    }

    async onRecordReset() {
        await this.onModelSelected({ technical: false, label: false });
    }

    async onResIdUpdate(value) {
        if (this.state.resModel) {
            await this.props.record.update(
                { res_id: value[0], res_model: this.state.resModel },
                { save: true }
            );
        }
    }
}

/**
 * Return isDetailsPanelRecord = true to prevent multi edit when editing a focused record from the
 * details panel but not from the list rows.
 * @type ProxyHandler
 */
const isDetailsPanelRecordHandler = {
    get(target, prop, receiver) {
        return prop === "isDetailsPanelRecord" || Reflect.get(...arguments);
    },
};
