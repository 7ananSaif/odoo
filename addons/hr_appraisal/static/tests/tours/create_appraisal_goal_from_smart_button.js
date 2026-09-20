import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("appraisals_create_appraisal_goal_from_smart_button", {
    // starts from /odoo/appraisals/<appraisal_id>
    steps: () => [
        stepUtils.autoExpandMoreButtons(),
        {
            trigger: "button[name='action_open_goals']",
            content: "Click on Goals smart button",
            run: "click",
        },
        {
            trigger: "button:contains('New')",
            content: "Create a new appraisal goal for employee",
            run: "click",
        },
        {
            trigger: "h1 > div[name='name'] > input",
            content: "Fill mandatory goal name input",
            run: "fill Goal Name",
        },
        ...stepUtils.saveForm(),
    ],
});

registry.category("web_tour.tours").add("employees_create_appraisal_goal_from_smart_button", {
    // starts from /odoo/employees/<employee_id>
    steps: () => [
        stepUtils.autoExpandMoreButtons(),
        {
            trigger: "button[name='action_open_goals']",
            content: "Click on Goals smart button",
            run: "click",
        },
        {
            trigger: "button:contains('New')",
            content: "Create a new appraisal goal for employee",
            run: "click",
        },
        {
            trigger: "h1 > div[name='name'] > input",
            content: "Fill mandatory goal name input",
            run: "fill Goal Name",
        },
        ...stepUtils.saveForm(),
    ],
});

