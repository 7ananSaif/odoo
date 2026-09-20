import { Asserts } from "./asserts";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("account_reports_audit", {
    url: "/odoo/action-account_reports.action_view_account_audit",
    steps: () => [
        {
            trigger: "button.o-kanban-button-new",
            content: "Create a new Audit",
            run: "click",
        },
        {
            isActive: ["auto"],
            trigger: ".modal",
            content: "Wait for the modal to open",
        },
        {
            trigger: "div[name='return_type_id'] .o_selection_badge:contains('Audit')",
            content: "Select the Return Type",
            run: "click",
        },
        {
            trigger: ".modal-footer button.btn-primary",
            content: "Generate the Audit",
            run: "click",
        },
        {
            trigger: "a[data-tooltip='Back to \"Audit\"']",
            content: "Back to the Audit Kanban",
            run: "click",
        },
        {
            trigger: ".o_kanban_record:nth-child(1) a[name='action_open_audit_balances']",
            content: "Open the Balances Part of the Audit",
            run: "click",
        },
        {
            trigger: ".o_data_row .o_data_cell",
            content: "Open the chatter for the first row",
            run: "click",
        },
        {
            content: "Add a log note",
            trigger: ".o-mail-Chatter-logNote",
            run: "click",
        },
        {
            content: "Add text to annotate",
            trigger: ".o-mail-Composer-inputContainer textarea",
            run: "edit Annotation from the audit",
        },
        {
            content: "Submit by logging the note",
            trigger: ".o-mail-Composer-send",
            run: "click",
        },
        {
            content: "Annotation is posted",
            trigger: ".o-mail-Message:last-child .o-mail-Message-textContent",
            run: async () => {
                const message = document.querySelector(
                    ".o-mail-Message:last-child .o-mail-Message-textContent"
                ).innerText;
                Asserts.isEqual(message, "Annotation from the audit");
                const annotation = document.querySelector(".o_account_reports_annotation");
                Asserts.isEqual(annotation.innerText.split("Annotated for").length, 2);
            },
        },
        {
            content: "Close Chatter",
            trigger: ".o_control_panel .btn-secondary[data-tooltip='Chatter']",
            run: "click",
        },
        {
            content: "Check that the chatter is closed",
            trigger: ".o_account_report_chatter:not(:visible)",
        },
    ],
});
