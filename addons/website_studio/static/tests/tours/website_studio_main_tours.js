import { registry } from "@web/core/registry";
import { changeOptionInPopover } from "@website/js/tours/tour_utils";

registry.category("web_tour.tours").add("website_studio_listing_and_page", {
    url: "/odoo/action-studio?debug=1&mode=home_menu",
    steps: () => [
        {
            trigger: "a.o_menuitem:contains('StudioApp')",
            run: "click",
        },
        {
            trigger: ".o_menu_sections button:contains('Model Pages')",
            run: "click",
        },
        {
            content: "Create a listing page",
            trigger: ".o-kanban-button-new",
            run: "click",
        },
        {
            content: "Set the name of the page",
            trigger: "div[name='name'] input",
            run: "edit MyCustom Name && press Tab",
        },
        {
            trigger: "div[name='name_slugified'] input:value(mycustom-name)",
        },
        {
            content: "listing is displayed in the menu by default",
            trigger: "div[name='use_menu'] input:checked",
        },
        {
            content:
                "creating a listing automatically creates a detailed page for each record to be consulted separately",
            trigger: "div[name='auto_single_page'] input:checked",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            trigger: ".o_back_button",
            run: "click",
        },
        {
            trigger: ".o_kanban_view .o_kanban_renderer .o_kanban_record div[data-section='title']:contains('MyCustom Name')",
        },
    ],
});

registry.category("web_tour.tours").add("website_studio_listing_without_page", {
    url: "/odoo/action-studio?debug=1&mode=home_menu",
    steps: () => [
        {
            trigger: "a.o_menuitem:contains('StudioApp')",
            run: "click",
        },
        {
            trigger: ".o_menu_sections button:contains('Model Pages')",
            run: "click",
        },
        {
            content: "Create a listing page",
            trigger: ".o-kanban-button-new",
            run: "click",
        },
        {
            content: "Set the name of the page",
            trigger: "div[name='name'] input",
            run: "edit MyCustom Name && press Tab",
        },
        {
            trigger: "div[name='name_slugified'] input:value(mycustom-name)",
        },
        {
            content: "listing is displayed in the menu by default",
            trigger: "div[name='use_menu'] input:checked",
        },
        {
            content:
                "creating a listing automatically creates a detailed page for each record to be consulted separately",
            trigger: "div[name='auto_single_page'] input:checked",
        },
        {
            content: "Uncheck the toggle and only create the listing",
            trigger: "div[name='auto_single_page'] input",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            trigger: ".o_back_button",
            run: "click",
        },
        {
            trigger: ".o_kanban_view .o_kanban_renderer .o_kanban_record div[data-section='title']:contains('MyCustom Name')",
        },
    ],
});

registry.category("web_tour.tours").add("website_studio_website_form", {
    steps: () => [
        {
            trigger: ".o-website-btn-custo-primary:contains('Edit')",
            run: "click",
        },
        {
            trigger: "#snippet_groups",
        },
        {
            trigger: ":iframe .odoo-editor-editable .s_website_form h2",
            run: "click",
        },
        ...changeOptionInPopover("Form", "Action", "More models"),
        {
            trigger: ".modal .o_list_view"
        },
        {
            trigger: ".modal .o_searchview_input",
            run: "edit x_test_model"
        },
        {
            trigger: ".o_searchview_autocomplete .o-dropdown-item.focus",
            run: "press Enter"
        },
        {
            trigger: ".modal .o_data_row:contains(x_test_model) .o_data_cell",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) div[data-action-id='studioToggleFormAccess'] input:checked",
        },
        {
            trigger: ":iframe form[data-model_name='x_test_model']",
        },
        {
            trigger: ".o-snippets-top-actions button[data-action='save']",
            run: "click",
        },
        {
            trigger: ".o_website_preview:not(.editor_enable) :iframe form[data-model_name='x_test_model']",
        },
    ]
});
