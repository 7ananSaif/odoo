import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";

export class SalaryRuleListController extends ListController {

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.state = useState({
            disabled: false,
        });
    }

    async onReload() {
        return this.actionService.doAction({type: "ir.actions.client", tag: "soft_reload"});
    }

    async onClose() {
        return this.actionService.doAction({type: "ir.actions.act_window_close"});
    }

    async updatePayrollProperties() {
        this.state.disabled = true;
        const selected_rules = await this.model.root.getResIds(true);
        if (selected_rules.length < 1) return;
        try {
            await this.orm.call(
                "hr.salary.rule",
                "update_properties_definition_domain",
                [selected_rules, this.props.context.active_model],
            );
            await this.onClose();
            await this.onReload();
        } finally {
            this.state.disabled = false;
        }
    }
}
export const salaryRuleListController = {
    ...listView,
    Controller: SalaryRuleListController,
    buttonTemplate: "hr_payroll.SalaryRuleListController.Buttons",
};

registry.category("views").add("hr_salary_rule_list", salaryRuleListController);