import { Plugin } from "@html_editor/plugin";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export class SearchbarOptionPlugin extends Plugin {
    static id = "website_appointment.searchbarOption";

    resources = {
        searchbar_option_display_items: [
            {
                label: _t("Description"),
                dataAttribute: "displayDescription",
                dependency: "search_appointment_opt",
            },
        ],
    };
}

registry
    .category("website-plugins")
    .add(SearchbarOptionPlugin.id, SearchbarOptionPlugin);
