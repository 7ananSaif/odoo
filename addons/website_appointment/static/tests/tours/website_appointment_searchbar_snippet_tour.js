import {
    changeOptionInPopover,
    clickOnSnippet,
    clickOnSave,
    insertSnippet,
    registerWebsitePreviewTour,
} from "@website/js/tours/tour_utils";

registerWebsitePreviewTour("test_searchbar_within_appointments", {
    url: "/",
    edition: true,
}, () => [
    ...insertSnippet({ id: "s_searchbar_input", name: "Search" }),
    ...clickOnSnippet({ id: "s_searchbar_input", name: "Search" }),
    ...changeOptionInPopover("Search", "Search within", "Appointments"),
    {
        content: "Limit search to 'Appointments'",
        trigger: ':iframe .s_searchbar_input[action="/appointment"]',
    },
    ...clickOnSave(),
    {
        content: "Enter search term",
        trigger: ":iframe .o_searchbar_form input",
        run: "edit yoga session",
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
