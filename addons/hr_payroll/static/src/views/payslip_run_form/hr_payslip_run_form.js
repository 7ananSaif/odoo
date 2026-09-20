import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { addFieldDependencies, extractFieldsFromArchInfo } from "@web/model/relational_model/utils";
import { serializeDate } from "@web/core/l10n/dates";

export class PayslipBatchFormController extends FormController {
    setup() {
        super.setup();
        const { activeFields, fields } = extractFieldsFromArchInfo(
            this.archInfo,
            this.props.fields
        );
        addFieldDependencies(activeFields, fields, [{name: this.archInfo.name, type:"string"}]);
        this.actionService = useService("action");
    }

    get payRunValid() {
        return this.model.root && this.model.root.data.date_start && this.model.root.data.date_end;
    }

    async selectEmployees() {
        const employeeListAction = await this.orm.call("hr.payslip.run", "action_payroll_hr_version_list_view_payrun", [
            [this.model.root.resId],
            serializeDate(this.model.root.data.date_start),
            serializeDate(this.model.root.data.date_end),
            this.model.root.data.structure_id?.id,
            this.model.root.data.company_id?.id,
            this.model.root.data.schedule_pay,
        ]);
        return this.actionService.doAction({
            ...employeeListAction,
            help: markup(employeeListAction.help),
            context: {
                raw_record: this.model.root.data,
            },
        });
    }
}

registry.category("views").add("hr_payslip_batch_form", {
    ...formView,
    Controller: PayslipBatchFormController,
    buttonTemplate: "hr_payroll.PayslipBatchFormView.Buttons"
});
