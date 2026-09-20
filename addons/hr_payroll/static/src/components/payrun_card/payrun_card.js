import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { formatMonetary } from "@web/views/fields/formatters";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useDeleteRecords } from "@web/views/view_hook";
import { PayRunButtonBox } from "./button_box/payrun_button_box";
import { ViewButton } from "@web/views/view_button/view_button";
import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { Field } from "@web/views/fields/field";
import { Widget } from "@web/views/widgets/widget";
import { StatusBubble } from "../status_bubble/status_bubble";
import { MoreInfo } from "./more_info/payrun_more_info";

export class PayRunCard extends Component {
    static template = "hr_payroll.PayRunCard";
    static props = {
        record: { type: Object },
    };
    static components = {
        Dropdown,
        DropdownItem,
        PayRunButtonBox,
        ViewButton,
        Field,
        Widget,
        StatusBubble,
        MoreInfo,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.deleteRecordsWithConfirmation = useDeleteRecords(this.props.record.model);
        this.formatMonetary = formatMonetary;
        this.evaluateBooleanExpr = evaluateBooleanExpr;
    }

    get payrun() {
        return this.props.record.data;
    }

    get dateStart() {
        return luxon.DateTime.fromISO(this.props.record.data.date_start, {
            locale: this.env.model.config.context.lang.replace("_", "-"),
        }).toLocaleString(luxon.DateTime.DATE_MED);
    }

    get dateEnd() {
        return luxon.DateTime.fromISO(this.props.record.data.date_end, {
            locale: this.env.model.config.context.lang.replace("_", "-"),
        }).toLocaleString(luxon.DateTime.DATE_MED);
    }

    async onChange(ev) {
        await this.props.record.update({ name: ev.target.value });
        await this.props.record.save();
    }
}
