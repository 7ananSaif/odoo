import { ControlPanel } from "@web/search/control_panel/control_panel";
import { patch } from "@web/core/utils/patch";

patch(ControlPanel.prototype, {
    switchView(viewType, newWindow) {
        const searchModel = this.env.searchModel;
        const filterNamesToDisable = ["kanban_date_filter", "kanban_hour_filter"];
        const filtersToDisable = Object.values(searchModel.searchItems).filter(
            (sm) =>
                filterNamesToDisable.includes(sm.name) &&
                searchModel.query.some((q) => q.searchItemId === sm.id)
        );
        for (const filter of filtersToDisable) {
            searchModel.toggleSearchItem(filter.id);
        }
        super.switchView(...arguments);
    },
});
