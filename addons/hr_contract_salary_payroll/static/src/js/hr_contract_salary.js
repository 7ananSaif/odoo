import { SalaryPackage } from "@hr_contract_salary/interactions/hr_contract_salary";
import { patch } from "@web/core/utils/patch";

patch(SalaryPackage.prototype, {
    updateGrossToNetModal(data) {
        this.el.querySelector("main.modal-body").replaceChildren();
        this.renderAt("hr_contract_salary_payroll.salary_package_brut_to_net_modal", {
            "datas": data.payslip_lines,
        }, this.el.querySelector("main.modal-body"));
        super.updateGrossToNetModal(data);
    },
});
