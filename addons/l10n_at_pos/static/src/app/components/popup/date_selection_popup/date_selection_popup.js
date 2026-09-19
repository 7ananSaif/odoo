import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";

export class DateSelectionPopup extends Component {
    static template = "l10n_at_pos.DateSelectionPopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        confirmLabel: { type: String, optional: true },
        getPayload: Function,
        close: Function,
    };
    static defaultProps = {
        confirmLabel: _t("Print"),
        title: _t("DatePicker"),
    };

    setup() {
        this.state = useState({
            period: "monthly",
            selectedDate: this.defaultDate(),
        });
    }
    defaultDate() {
        const currentDate = new Date();
        const year = currentDate.getFullYear();
        const month = currentDate.getMonth(); // 0-based index (0 = January)
        const lastMonthYear = month === 0 ? year - 1 : year;
        const lastMonth = month % 12; // month will be already 1 index less
        return `${lastMonthYear}-${String(lastMonth).padStart(2, "0")}`;
    }
    confirm() {
        this.props.getPayload({
            selectedDate: this.state.selectedDate,
            period: this.state.period,
        });
        this.props.close();
    }
}
