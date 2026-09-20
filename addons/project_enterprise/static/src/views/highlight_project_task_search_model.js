import { SearchModel } from "@web/search/search_model";
import { Domain } from "@web/core/domain";

export class HighlightProjectTaskSearchModel extends SearchModel {
    exportState() {
        return {
            ...super.exportState(),
            highlightIds: this.highlightIds,
        };
    }

    _importState(state) {
        this.highlightIds = state.highlightPlannedIds;
        super._importState(state);
    }

    _getDomain(params = {}) {
        let domain = super._getDomain(params);
        if (this.highlightIds?.length) {
            domain = Domain.and([domain, [["id", "in", this.highlightIds]]]);
            domain = params.raw ? domain : domain.toList();
        }
        return domain;
    }

    async load(config) {
        await super.load(config);
        if (this.context && this.context.highlight_conflicting_task) {
            this.highlightIds = await this.orm.search("project.task", [
                ["planning_overlap", "!=", false],
            ]);
        }
    }

    deactivateGroup(groupId) {
        if (this._getHighlightSearchItems()?.groupId === groupId) {
            this.highlightIds = null;
        }
        super.deactivateGroup(groupId);
    }

    toggleHighlightPlannedFilter(highlightPlannedIds) {
        const highlightPlannedSearchItems = this._getHighlightSearchItems();
        if (highlightPlannedIds) {
            this.highlightIds = highlightPlannedIds;
            if (highlightPlannedSearchItems) {
                if (
                    this.query.find(
                        (queryElem) => queryElem.searchItemId === highlightPlannedSearchItems.id
                    )
                ) {
                    this._notify();
                } else {
                    this.toggleSearchItem(highlightPlannedSearchItems.id);
                }
            }
        } else if (highlightPlannedSearchItems) {
            this.deactivateGroup(highlightPlannedSearchItems.groupId);
        }
    }

    _getHighlightSearchItems() {
        return Object.values(this.searchItems).find((v) => v.name === "conflict_task");
    }
}
