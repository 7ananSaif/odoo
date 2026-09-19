import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";
import { accountTourSteps } from "@account/js/tours/account";

registry.category("web_tour.tours").add("account_accountant_bank_rec_widget", {
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
            content: "Create New statement",
            trigger: "button.o-kanban-button-new",
            run: "click",
        },
        {
            trigger: "div.o_bank_reconciliation_quick_create",
        },
        {
            content: "Write Label",
            trigger: "div[name='payment_ref'] input",
            run: "edit test",
        },
        {
            content: "Add a amount",
            trigger: "div[name='amount'] input",
            run: "edit 100",
        },
        {
            content: "Save & close",
            trigger: "div.button_group button.o_kanban_edit",
            run: "click",
        },
        {
            content: "Statement is created",
            trigger: "div[name='bank_statement_line']",
        },
        {
            content: "Unfold statement line",
            trigger: "div[name='bank_statement_line']",
            run: "click",
        },
        {
            content: "line is unfolded",
            trigger: "div.o_button_line",
        },
        {
            content: "Set Partner",
            trigger: "button.btn-primary span:contains('Set Partner')",
            run: "click",
        },
        {
            content: "Search view is opened",
            trigger: "div.modal-dialog",
        },
        {
            content: "Select first partner",
            trigger: "tbody > tr > td[name='complete_name']",
            run: "click",
        },
        {
            content: "Partner is set",
            trigger: "span[name='statement_line_partner_name']",
        },
        {
            content: "Fold statement line",
            trigger: "div[name='bank_statement_line']",
            run: "click",
        },
        {
            content: "Statement line is reconciled because move with same partner and amount",
            trigger: "div[name='reconciled_line_name']",
        },
        {
            content: "Create New statement",
            trigger: "button.o-kanban-button-new",
            run: "click",
        },
        {
            trigger: "div.o_bank_reconciliation_quick_create",
        },
        {
            content: "Write Label",
            trigger: "div[name='payment_ref'] input",
            run: "edit test",
        },
        {
            content: "Add a amount",
            trigger: "div[name='amount'] input",
            run: "edit 150",
        },
        {
            content: "Save & close",
            trigger: "div.button_group button.o_kanban_edit",
            run: "click",
        },
        {
            content: "Open Ellipsis button",
            trigger: "button.btn-secondary i.oi-ellipsis-v",
            run: "click",
        },
        {
            content: "Reconcile button",
            trigger: "span.btn-link:contains('Reconcile')",
            run: "click",
        },
        {
            content: "Search view is opened",
            trigger: "div.modal-dialog",
        },
        {
            content: "Select first move line",
            trigger: "tbody > tr > td[name='partner_id']",
            run: "click",
        },
        {
            content: "Statement line is reconciled",
            trigger: "div[name='reconciled_line_name']",
        },
    ],
});
