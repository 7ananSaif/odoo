import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { belgiumAdditionalPersonalInfo } from "./belgium_additional_personal_info";
import {
    salaryConfigTourStart,
    salaryConfigTourPersonalInfo,
    salaryConfigTourSubmitAndSign,
} from "@hr_contract_salary/../tests/tours/hr_contract_salary_employee_flow_tour";

patch(registry.category("web_tour.tours").get("hr_contract_salary_employee_flow_tour"), {
    steps() {
        return [
            ...salaryConfigTourStart(),
            ...salaryConfigTourPersonalInfo(),
            ...belgiumAdditionalPersonalInfo(),
            ...salaryConfigTourSubmitAndSign(),
        ]
    }
});
