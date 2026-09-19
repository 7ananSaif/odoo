import { inputFiles } from "@web/../tests/utils";
import { registry } from "@web/core/registry";

async function uploadTestFile(inputId) {
    const testFile = new File(["hello, world"], "hello_world.pdf", { type: "application/pdf" });
    await inputFiles(`#${inputId}Input input`, [testFile]);
}

function fillDate(anchor, value) {
    anchor.value = value;
    // to trigger t-model updating component state
    anchor.dispatchEvent(new Event("input"));
    anchor.dispatchEvent(new Event("change"));
}

function endHolder(holderName, endDate, displayedEndDate) {
    return [
        {
            content: `End ${holderName}`,
            trigger: `tr:contains('${holderName}') td .fa-remove`,
            run: "click",
        },
        {
            content: "Enter end date",
            trigger: ".o_holder_end_dialog input",
            run() { fillDate(this.anchor, endDate) },
        },
        {
            content: "Submit",
            trigger: ".modal-footer button:contains('Remove Shareholder')",
            run: "click",
        },
        {
            trigger: `tr:contains('${holderName}') td:contains('${displayedEndDate}')`,
        },
    ];
}

function editHolder(newValues) {
    return [
        ...Object.keys(newValues).map(key => {
            let trigger = `.o_holder_edit_dialog #${key}Input :is(input, select)`;
            if (key === "doc") {
                // file input has special treatment as the input element is hidden
                trigger = `.o_holder_edit_dialog #${key}Input input:not(:visible)`;
            }
            const run = newValues[key];
            return {
                trigger,
                run,
            };
        }),
        {
            trigger: ".modal-footer button.btn-primary",
            run: "click",
        },
    ];
}

registry.category("web_tour.tours").add("request_ubo_portal_form_tour", {
    steps: () => [
        {
            content: "Open Cog menu",
            trigger: ".o_cp_action_menus .o-dropdown",
            run: "click",
        },
        {
            trigger: ".o-dropdown-item:contains('Request UBO Form')",
            run: "click",
        },
        {
            trigger: ".o_mail_send[name='action_send_mail']",
            run: "click",
        },
        {
            content: "Wait for modal to close",
            trigger: "body:not(:has(.o_mail_send))",
        },
    ],
});

registry.category("web_tour.tours").add("fill_ubo_portal_form_tour", {
    steps: () => [
        ...endHolder("Company Holder 1", "2025-05-13", "May 13, 2025"),
        ...endHolder("Company Holder 2", "2025-06-13", "Jun 13, 2025"),
        {
            content: "Return Company Holder 2",
            trigger: "tr:contains('Company Holder 2') td .fa-undo",
            run: "click",
        },
        {
            trigger: "tr:contains('Company Holder 2'):not(:contains('Jun 13, 2025'))",
        },
        {
            content: "Edit Company Holder 2",
            trigger: "tr:contains('Company Holder 2')",
            run: "click",
        },
        ...editHolder({
            name: "edit Hesham Saleh",
            country: "selectByLabel Egypt",
            birthDate() { fillDate(this.anchor, "2001-11-24") },
            id: "edit 1234552",
            pep: "click", // to set it to true
            async doc() { await uploadTestFile("doc") },
            expirationDate() { fillDate(this.anchor, "2026-12-31") },
            startDate() { fillDate(this.anchor, "2025-03-30") },
            controlMethod: "select co_1",
            async ownership(helpers) {
                await helpers.edit("43");
                // because ownership value affects voting rights
                // it needs to lose focus then before overwriting voting rights
                await helpers.press("Enter");
            },
            votingRights: "edit 45",
        }),
        {
            content: "Add new holder",
            trigger: "button:contains('Add Beneficial Owner')",
            run: "click",
        },
        ...editHolder({
            name: "edit Brandon Freeman",
            country: "selectByLabel Belgium",
            birthDate() { fillDate(this.anchor, "1980-02-21") },
            id: "edit 3324",
            pep: "click",
            async doc() { await uploadTestFile("doc") },
            expirationDate() { fillDate(this.anchor, "2027-12-31") },
            startDate() { fillDate(this.anchor, "2024-12-01") },
            controlMethod: "select co_3",
            role: "selectByLabel Chairman of the Board",
        }),
        {
            content: "Edit Brandon Freeman",
            trigger: "tr:contains('Brandon Freeman')",
            run: "click",
        },
        {
            content: "Remove uploaded file",
            trigger: ".o_holder_edit_dialog #docInput button.fa-trash",
            run: "click",
        },
        ...editHolder({
            pep: "click", // to set it to false
        }),
        {
            content: "Sign the form",
            trigger: "input[name='rep_name']",
            run: "edit Nicole Ford",
        },
        {
            trigger: "input[name='rep_position']",
            run: "edit CEO",
        },
        {
            trigger: "button.btn-primary:contains('Submit')",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Wait for thanks page",
            trigger: "h4:contains('Your UBO Declaration Has Been Submitted!')",
        },
    ],
});
