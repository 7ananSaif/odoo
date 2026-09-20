import { defineModels } from "@web/../tests/web_test_helpers";
import { hrModels } from "@hr/../tests/hr_test_helpers";
import { HrEmployee } from "@hr_payroll/../tests/mock_server/mock_models/hr_employee";
import { HrPayslipRun } from "@hr_payroll/../tests/mock_server/mock_models/hr_payslip_run";
import { HrPayslip } from "@hr_payroll/../tests/mock_server/mock_models/hr_payslip";
import { ResCurrency } from "@hr_payroll/../tests/mock_server/mock_models/res_currency";
import { HrSalaryRule } from "@hr_payroll/../tests/mock_server/mock_models/hr_salary_rule"

export function defineHrPayrollModels() {
    return defineModels(hrPayrollModels);
}

export const hrPayrollModels = {
    ...hrModels,
    HrEmployee,
    HrPayslip,
    HrPayslipRun,
    ResCurrency,
    HrSalaryRule,
};
