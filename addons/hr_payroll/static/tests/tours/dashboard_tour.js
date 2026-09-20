import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add('payroll_dashboard_ui_tour', {
    url: '/odoo',
    steps: () => [
    stepUtils.showAppsMenuItem(),
    {
        content: "Open payroll app",
        trigger: '.o_app[data-menu-xmlid="hr_work_entry_enterprise.menu_hr_payroll_root"]',
        run: "click",
    },
    {
        content: "Employees without running contracts",
        trigger: 'a:contains("Employees Without Running Contracts")',
        run: "click",
    },
    {
        content: "Open employee profile",
        trigger: 'tr.o_data_row td[name="name"]',
        run: "click",
    },
    {
        content: "Open contract tab",
        trigger: 'a[name="payroll_information"]',
        run: "click",
    },
    {
        content: "Input contract date start",
        trigger: '.o_field_widget[name="contract_date_start"] input',
        run: "edit 17/09/2018",
    },
    {
        content: "Go back to dashboard",
        trigger: 'a[data-menu-xmlid="hr_payroll.menu_hr_payroll_dashboard_root"]',
        run: "click",
    },
    {
        content: "Check that the no contract error is gone",
        trigger: 'h2:contains("Warning")',
    },
    {
        content: "There should be no no running contract issue on the dashboard",
        trigger: "body:not(:has(.o_hr_payroll_dashboard_block div.row div.col a:contains(Employees Without Running Contracts)))",
    },
    {
        content: "Create a new note",
        trigger: 'button.o_hr_payroll_todo_create',
        run: "click",
    },
    {
        content: "Set a name",
        trigger: 'li.o_hr_payroll_todo_tab input',
        run: "edit Dashboard Todo List && click body",
    },
    {
        trigger: "li.o_hr_payroll_todo_tab a.active:contains(Dashboard Todo List)",
    },
    {
        content: "Edit the note in dashboard view",
        trigger: 'div.o_hr_payroll_todo_value',
        run: 'click',
    },
    {
        content: "Write in the note",
        trigger: ".note-editable.odoo-editor-editable",
        run: "editor Todo List",
    }
]});
