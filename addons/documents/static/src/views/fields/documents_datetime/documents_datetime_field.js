import { Component } from "@odoo/owl";
import { formatDateTime } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { DocumentsDatetimeBtnField } from "../documents_datetime_btn/documents_datetime_btn_field";

export class DocumentsDatetimeField extends Component {
    static template = "documents.DocumentsDatetimeField";
    static props = {
        ...standardFieldProps,
        label: { type: String, optional: true },
    };
    static components = {
        DocumentsDatetimeBtnField,
    };

    async onRemove() {
        this.props.record.update({ [this.props.name]: false });
    }

    get formattedLocalExpirationDate() {
        return formatDateTime(this.props.record.data[this.props.name], {
            format: localization.dateFormat,
        });
    }
}

export const documentsDatetimeField = {
    component: DocumentsDatetimeField,
    supportedTypes: ["datetime"],
    extractProps: ({ string }, dynamicInfo) => ({
        label: string,
        readonly: dynamicInfo.readonly,
    }),
};

registry.category("fields").add("documents_datetime", documentsDatetimeField);
