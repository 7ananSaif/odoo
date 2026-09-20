import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("hr_contract_salary_payroll_tour", {
    steps: () => [
        {
            content: "Check salary package resume exists",
            trigger: 'div[name="salary_package_resume"]',
        },
    ],
});
