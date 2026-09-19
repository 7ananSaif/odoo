import { registry } from "@web/core/registry";

function assert(current, expected, info) {
    if (current !== expected) {
        fail(info + ': "' + current + '" instead of "' + expected + '".');
    }
}

function fail(errorMessage) {
    console.error(errorMessage);
}

const SHEETNAME = "Res Partner Test Spreadsheet";
registry.category("web_tour.tours").add("spreadsheet_open_pivot_sheet", {
    steps: () => [
        {
            trigger: '.o_app[data-menu-xmlid="documents.menu_root"]',
            content: "Open document app",
            run: "click",
        },
        {
            trigger: '.o_documents_title:contains("Folders")',
            content: "check if the folders are loaded",
        },
        {
            trigger: 'li[title="Company"] header button',
            content: "Open the company folder",
            run: "click",
        },
        {
            trigger: "span.o_search_panel_label_title:contains('Test Folder')",
            content: "Open the test folder (in company folder)",
            run: "click",
        },
        {
            trigger: `button.o_switch_view.o_list`,
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: `.o_data_row:contains("${SHEETNAME}") .o_documents_mimetype_icon`,
            content: "Open the sheet",
            run: "click",
        },
        {
            trigger: "div.o_topbar_filter_icon",
            content: "Open Filters",
            run: "click",
        },
        {
            trigger: "button.o-edit-global-filters",
            content: "Open Filters Side Panel",
            run: "click",
        },
        {
            trigger: "div.pivot_filter_section",
            content: "",
            run: function (actions) {
                const pivots = document.querySelectorAll("div.pivot_filter_section");
                assert(pivots.length, 1, "There should be one filter");
                const pivot = pivots[0];
                assert(
                    pivot.querySelector("span.o_side_panel_filter_label").textContent,
                    "MyFilter1",
                    "Invalid filter name"
                );
                actions.click(pivot.querySelector(".pivot_filter_section"));
            },
        },
        {
            trigger: ".o-sp-breadcrumb",
            content: "Go back to Document App",
            run: "click",
        },
        {
            trigger: `.o_data_cell:contains("${SHEETNAME}")`,
            content: "Sheet is visible in Documents",
        },
    ],
});
