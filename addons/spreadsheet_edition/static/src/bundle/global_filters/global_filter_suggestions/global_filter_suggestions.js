import { Component, onWillStart } from "@odoo/owl";
import { components, stores } from "@odoo/o-spreadsheet";
import { GlobalFilterSuggestionsStore } from "./global_filter_suggestions_store";

const { Section } = components;
const { useLocalStore } = stores;

export class GlobalFilterSuggestions extends Component {
    static template = "spreadsheet_edition.GlobalFilterSuggestions";
    static components = { Section };
    static props = {};

    setup() {
        const store = useLocalStore(GlobalFilterSuggestionsStore);
        onWillStart(async () => {
            this.suggestions = await store.suggestionsPromise;
        });
    }

    onSuggestionClick(suggestion) {
        this.env.openSidePanel("RELATION_FILTER_SIDE_PANEL", {
            label: suggestion.label,
            modelName: suggestion.modelName,
            modelDisplayName: suggestion.modelDisplayName,
            fieldMatching: suggestion.fieldMatching,
        });
    }
}
