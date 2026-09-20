import { ProgressBarField, progressBarField } from "@web/views/fields/progress_bar/progress_bar_field"
import { registry } from "@web/core/registry";
export class AccountAuditProgressbar extends ProgressBarField {
    static template = "account_reports.AccountAuditProgresbar";

    get progressBarColorClass() {
        if (this.maxValue == 0) {
            return "";
        }
        return this.currentValue > this.maxValue ? this.props.overflowClass : "bg-success";
    }

    get maxValue() {
        return this.props.record.data[this.maxValueField];
    }

    get hasMaxValue() {
        return this.props.record.data.hasOwnProperty(this.maxValueField)
    }
}

export const AccountAuditProgressBarField = {
    ...progressBarField,
    component: AccountAuditProgressbar,
};

registry.category("fields").add("account_audit_progressbar", AccountAuditProgressBarField);

