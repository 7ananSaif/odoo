import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { CharField } from "@web/views/fields/char/char_field";

import { Component, toRaw } from "@odoo/owl";
import { DocumentsSearchPanelUserFolderId } from "@documents/views/fields/documents_user_folder_id_char/documents_search_panel_user_folder_id";

export class DocumentsUserFolderIdCharField extends Component {
    static components = { DocumentsSearchPanelUserFolderId };
    static props = {
        ...CharField.props,
        extraFields: { type: Array, optional: true },
        ulClass: { type: String, optional: true },
    };
    static template = "documents.DocumentsUserFolderIdChar";

    /**
     * Change current value and optionally other fields
     *
     * @param val
     * @param {Object} extra Additional fields values to update
     * @return {Promise<void>}
     */
    async onChange(val, extra = {}) {
        const values = { [this.props.name]: val };
        this.props.extraFields.forEach((fieldName) => {
            values[fieldName] = extra[fieldName];
        });
        await this.props.record.update(values);
    }

    get value() {
        return toRaw(this.props.record.data[this.props.name]);
    }
}

export const documentsUserFolderIdCharField = {
    component: DocumentsUserFolderIdCharField,
    displayName: _t("Destination"),
    supportedTypes: ["char", "text"],
    extractProps: ({ options }) => ({
        extraFields: options.extraUpdateFields || [],
        ulClass: options.ulClass || "",
    }),
};

registry.category("fields").add("documents_user_folder_id_char", documentsUserFolderIdCharField);
