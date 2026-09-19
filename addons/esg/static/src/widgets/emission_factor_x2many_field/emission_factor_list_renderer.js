import { markup } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ListRenderer } from "@web/views/list/list_renderer";

export class EmissionFactorListRenderer extends ListRenderer {
    _getEsgAssignationPlaceholder(fieldName, formatted = false) {
        const placeholders = {
            account_id: _t("Any Account"),
            product_id: _t("Any Product"),
            partner_id: _t("Any Partner"),
        };

        let placeholder = placeholders[fieldName] || "";
        if (formatted) {
            placeholder = markup`<span class="text-muted fst-italic">${placeholder}</span>`;
        }
        return placeholder;
    }

    getFormattedValue(column, record) {
        return record.data[column.name]
            ? super.getFormattedValue(column, record)
            : this._getEsgAssignationPlaceholder(column.name, true);
    }

    getCellTitle(column, record) {
        return record.data[column.name]
            ? super.getCellTitle(column, record)
            : this._getEsgAssignationPlaceholder(column.name);
    }
}
