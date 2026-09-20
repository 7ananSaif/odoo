import { SearchModel } from "@web/search/search_model";
import { patch } from "@web/core/utils/patch";

patch(SearchModel.prototype, {
    get facets() {
        const result = super.facets;
        const excludedIds = Object.values(this.searchItems)
            .filter((sm) => ["kanban_date_filter", "kanban_hour_filter"].includes(sm.name))
            .map((sm) => sm.groupId);
        return result.filter((f) => !excludedIds.includes(f.groupId));
    },
});
