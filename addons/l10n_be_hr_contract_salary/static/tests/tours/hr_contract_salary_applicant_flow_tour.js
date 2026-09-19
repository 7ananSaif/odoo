import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import {
    salaryConfigTourStart,
    salaryConfigTourPersonalInfo,
    salaryConfigTourSubmitAndSign,
} from "@hr_contract_salary/../tests/tours/hr_contract_salary_applicant_flow_tour";

patch(registry.category("web_tour.tours").get("hr_contract_salary_applicant_flow_tour"), {
    steps() {
        return [
            ...salaryConfigTourStart(),
            ...salaryConfigTourPersonalInfo(),
            {
                content: "Language",
                trigger: "select[name=lang]:not(:visible)",
                run: "selectByLabel English",
            },
            ...salaryConfigTourSubmitAndSign(),
        ]
    }
});
