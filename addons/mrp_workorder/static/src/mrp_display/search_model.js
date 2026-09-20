import { _t } from "@web/core/l10n/translation";
import { SearchModel } from "@web/search/search_model";
import { useState } from "@odoo/owl";

export class MrpDisplaySearchModel extends SearchModel {
    setup(services, args) {
        super.setup(services);
        this.state = useState({
            workorderFilters: [
                {
                    name: "ready",
                    string: _t("To Do"),
                    isActive: !!args.search_default_ready,
                },
                {
                    name: "blocked",
                    string: _t("Blocked"),
                    isActive: !!args.search_default_blocked,
                },
                {
                    name: "progress",
                    string: _t("In Progress"),
                    isActive: !!args.search_default_progress,
                },
            ],
        });
        this.workorders = true;
    }

    _getIrFilterDescription(params = {}) {
        // Save workorder filters in favorite context
        const { irFilter, preFavorite } = super._getIrFilterDescription(params);
        if (this.workorders) {
            const activeFilterIds = this.state.workorderFilters.reduce(
                (acc, i) => (i.isActive ? [...acc, i.name] : acc),
                []
            );
            irFilter.context.wo_active_filters = activeFilterIds;
            preFavorite.context.wo_active_filters = activeFilterIds;
        }
        return { preFavorite, irFilter };
    }

    toggleSearchItem(searchItemId) {
        // Retrieve saved workorder filters from context or reset WO filters when enabling/disabling a favorite respectively
        const { type, context } = this.searchItems[searchItemId];
        if (this.workorders && type === "favorite") {
            const { wo_active_filters } = context;
            const removeFavorite =
                !wo_active_filters ||
                this.query.some((queryElem) => queryElem.searchItemId === searchItemId);
            for (const filter of this.state.workorderFilters) {
                filter.isActive = !removeFavorite && wo_active_filters.includes(filter.name);
            }
        }
        return super.toggleSearchItem(searchItemId);
    }

    setWorkcenterFilter(workcenters) {
        const filter = Object.values(this.searchItems).find(
            (si) => si.name === "shop_floor_this_station"
        );
        if (!filter) {
            return; // Avoid crashing when 'This Station' filter not installed.
        }
        filter.domain =
            "['|', ['workorder_ids.workcenter_id.id', 'in', [" +
            workcenters.map((wc) => wc.id).join(",") +
            "]], ['workorder_ids', '=', False]]";
        if (this.query.find((queryElem) => queryElem.searchItemId === filter.id)) {
            this._notify();
        }
    }

    removeMOFilter() {
        const facet = this.facets.find((f) => f.type === "field");
        if (facet) {
            this.deactivateGroup(facet.groupId);
        }
    }
}
