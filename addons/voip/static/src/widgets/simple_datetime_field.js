import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component } from "@odoo/owl";

export class SimpleDateTimeField extends Component {
    static template = "voip.SimpleDateTimeField";
    static props = {
        ...standardFieldProps,
    };

    get formattedDate() {
        const dt = this.props.record.data[this.props.name];
        if (!dt) {
            return "";
        }
        const now = luxon.DateTime.now();
        const time = dt.toLocaleString({ hour: "numeric", minute: "2-digit" });

        if (dt.hasSame(now, "day")) {
            return _t("Today, %(time)s", { time });
        }
        const yesterday = now.minus({ days: 1 });
        if (dt.hasSame(yesterday, "day")) {
            return _t("Yesterday, %(time)s", { time });
        }
        return dt.toLocaleString({
            month: "numeric",
            day: "2-digit",
            year: "2-digit",
            hour: "numeric",
            minute: "2-digit",
        });
    }
}

export const simpleDateTimeField = {
    component: SimpleDateTimeField,
    displayName: _t("Simple Date & Time"),
    supportedTypes: ["datetime"],
};

registry.category("fields").add("voip_simple_datetime", simpleDateTimeField);
