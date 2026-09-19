import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add('hr_payroll_work_entry_reset_tour', {
    steps: () => [
    {
        content: "Open payslip",
        trigger: '.o_data_row td:contains("Richard")',
        run: "click",
    },
    {
        content: "Click Work Entries smart button",
        trigger: 'button[name="action_open_work_entries"]',
        run: "click",
    },
    {
        content: "Wait for calendar to load with work entries",
        trigger: '.fc-daygrid-day .o_event',
    },
    {
        content: "Click on calendar cell with work entry to select it",
        trigger: '.fc-daygrid-day[data-date="2025-01-01"]',
        run: "click",
    },
    {
        content: "Click delete button",
        trigger: '.o_multi_selection_buttons button[data-tooltip="Delete"]',
        run: "click",
    },
    {
        content: "Click confirm button",
        trigger: '.modal-footer button:contains("Ok")',
        run: "click",
    },
    {
        content: "Wait for work entry to be deleted",
        trigger: '.fc-daygrid-day[data-date="2025-01-01"]:not(:has(.o_event))',
    },
    {
        content: "Click on calendar cell select it",
        trigger: '.fc-daygrid-day[data-date="2025-01-01"]',
        run: "click",
    },
    {
        content: "Click reset/undo button",
        trigger: '.o_multi_selection_buttons button[data-tooltip="Reset Selected Work Entries"]',
        run: "click",
    },
    {
        content: "Wait for work entry to be regenerated",
        trigger: '.fc-daygrid-day[data-date="2025-01-01"]:has(.o_event)',
    },
]});
