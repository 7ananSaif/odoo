import { markup } from "@odoo/owl";
import { serializeDate } from "@web/core/l10n/dates";
import { PayslipBatchFormController } from "@hr_payroll/views/payslip_run_form/hr_payslip_run_form"
import { patch } from "@web/core/utils/patch";

patch(PayslipBatchFormController.prototype, {
    async selectEmployees() {
        // In Hong Kong, we need the payroll group and scheme to properly handle the filtering of the employee.
        if (this.model.root.data.country_code === "HK")
        {
            const employeeListAction = await this.orm.call("hr.payslip.run", "action_l10n_hk_hr_version_list_view_payrun", [
                [this.model.root.resId],
                serializeDate(this.model.root.data.date_start),
                serializeDate(this.model.root.data.date_end),
                this.model.root.data.structure_id?.id,
                this.model.root.data.company_id?.id,
                this.model.root.data.schedule_pay,
                this.model.root.data.l10n_hk_payroll_group_id?.id,
                this.model.root.data.l10n_hk_payroll_scheme_id?.id,
            ]);
            return this.actionService.doAction({
                ...employeeListAction,
                help: markup(employeeListAction.help),
                context: {
                    raw_record: this.model.root.data,
                },
            });
        }
        return super.selectEmployees(...arguments);
    }
});
