import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("spreadsheet_save_multipage", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
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
            trigger: ".o_searchview_input",
            content: "click on search",
            run: "click",
        },
        {
            trigger: ".o_searchview_input",
            content: "fill in searchbar",
            run: `edit Res Partner Test Spreadsheet`,
        },
        {
            content: "find the right folder",
            trigger: ".o_searchview_autocomplete span:contains(Res Partner Test Spreadsheet)",
            run: "click",
        },
        {
            trigger: ".o_kanban_renderer .o_kanban_record:contains('Res Partner Test Spreadsheet')",
            content: "Check is rendered as single page",
            run: () => {
                const card = document.querySelectorAll(
                    ".o_kanban_renderer .o_kanban_record:first-child > div.o_kanban_stack"
                );
                if (card.length > 1) {
                    console.error("The card should not be rendered as multipage.");
                }
            },
        },
    ],
});
