import {
    changeOptionInPopover,
    clickOnSnippet,
    clickOnSave,
    insertSnippet,
    registerWebsitePreviewTour,
} from "@website/js/tours/tour_utils";

registerWebsitePreviewTour("test_searchbar_within_knowledge_articles", {
    url: "/",
    edition: true,
}, () => [
    ...insertSnippet({ id: "s_searchbar_input", name: "Search" }),
    ...clickOnSnippet({ id: "s_searchbar_input", name: "Search" }),
    ...changeOptionInPopover("Search", 'Search within', "Knowledge articles"),
    {
        content: "Limit search to 'Knowledge Articles'",
        trigger: ':iframe .s_searchbar_input[action="/website/search/knowledge"]',
    },
    ...clickOnSave(),
    {
        content: "Enter search term",
        trigger: ":iframe .o_searchbar_form input",
        run: "edit Test Filter knowledge Article",
    },
    {
        content: "Check that the number of results found is correct.",
        trigger: ":iframe .o_searchbar_form .o_dropdown_menu",
        run: function() {
            const dropdownItemsEls = this.anchor.querySelectorAll(".dropdown-item");
            if (dropdownItemsEls.length !== 1) {
                throw new Error("Tour failed: More/Less than 1 item is there for given keyword.");
            }
        }
    },
]);
