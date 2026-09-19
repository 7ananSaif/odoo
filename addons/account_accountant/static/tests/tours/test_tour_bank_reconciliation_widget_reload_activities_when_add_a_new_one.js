import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";
import { accountTourSteps } from "@account/js/tours/account";

registry
    .category("web_tour.tours")
    .add("account_accountant_bank_reconciliation_widget_reload_activies_when_add_a_new_one", {
        url: "/odoo",
        steps: () => [
            stepUtils.showAppsMenuItem(),
            ...accountTourSteps.goToAccountMenu("Open the accounting module"),

            {
                content: "Open the bank reconciliation widget",
                trigger: "a.oe_kanban_action span:contains('Bank')",
                run: "click",
            },
            {
                trigger: "div.o_bank_reconciliation_kanban_renderer",
            },
            {
                content: "Select statement line",
                trigger: "div[name='bank_statement_line']",
                run: "click",
            },
            {
                content: "Open chatter",
                trigger: "i.fa.fa-lg.fa-comments-o:not(:visible)",
                run: "click",
            },
            {
                content: "Chatter is opened",
                trigger: "div.o_bank_rec_widget_chatter_container",
            },
            {
                content: "Create an activity",
                trigger: "button.o-mail-Chatter-activity",
                run: "click",
            },
            {
                content: "Dialog activity is opened",
                trigger: "h4.modal-title:contains('Schedule Activity')",
            },
            {
                content: "Validate default activity",
                trigger: "button[name='action_schedule_activities']",
                run: "click",
            },
            {
                content: "Activity is reloaded in the widget",
                trigger: "div.activity-container > i.fa.fa-lg.fa-clock-o",
            },
        ],
    });
