/** @odoo-module **/

import { PropertiesField } from "@web/views/fields/properties/properties_field";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(PropertiesField.prototype, {
    _getPropertyEditWarningText() {
        if (this.props.record.resModel === 'account.asset') {
            return _t("You can add Property fields only on Assets with an Asset Model set.")
        }
        return super._getPropertyEditWarningText();
    }
});
