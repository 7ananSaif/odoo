import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { SalaryCalculatorFormController } from "./salary_calculator_form_controller";

export const SalaryCalculatorFormView = {
    ...formView,
    Controller: SalaryCalculatorFormController,
};

registry.category("views").add("salary_calculator_form_view", SalaryCalculatorFormView);
