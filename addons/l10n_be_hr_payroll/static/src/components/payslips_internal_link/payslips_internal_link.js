import { Component } from "@odoo/owl";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class PayslipsInternalLinkComponent extends Component {
    static template = "l10n_be_hr_payroll.PayslipsInternalLinkComponent";
    static props = { 
        ...standardWidgetProps,
        payslipsYear: { type: String, optional: true },
    };

    setup() {
        super.setup();
        this.dialog = useService("dialog");
    }

    async openNPayslips() {
        await this.props.record.save()
        this.dialog.add(FormViewDialog, {
            resId: this.props.record.resId,
            resModel: "hr.payslip.employee.depature.holiday.attests",
            size: "lg",
            title: _t("Current Year Payslips"),
            canExpand: false,
            onRecordSaved: async () => {
                await this.props.record.load();
            },
            context: {
                ...this.props.context,
                form_view_ref: "l10n_be_hr_payroll.view_hr_payroll_employee_departure_holiday_attests_n_payslips",
            },
        });
    }

    async openN1Payslips() {
        await this.props.record.save()
        this.dialog.add(FormViewDialog, {
            resId: this.props.record.resId,
            resModel: "hr.payslip.employee.depature.holiday.attests",
            size: "lg",
            title: _t("Previous Year Payslips"),
            canExpand: false,
            onRecordSaved: async () => {
                await this.props.record.load();
            },
            context: {
                ...this.props.context,
                form_view_ref: "l10n_be_hr_payroll.view_hr_payroll_employee_departure_holiday_attests_n1_payslips",
            },
        });
    }
}

export const payslipsInternalLinkComponent = {
    component: PayslipsInternalLinkComponent,
    extractProps: ({ attrs }) => {
        return {
            payslipsYear: attrs.payslips_year,
        };
    },
    fieldDependencies: [
        { name: "number_n_payslips_description", type: "char" },
        { name: "number_n1_payslips_description", type: "char" },
    ],
};

registry.category("view_widgets").add('payslips_internal_link', payslipsInternalLinkComponent);
