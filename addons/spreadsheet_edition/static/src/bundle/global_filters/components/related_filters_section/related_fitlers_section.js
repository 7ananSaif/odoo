import { Component } from "@odoo/owl";
import { components, stores } from "@odoo/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";

import { globalFieldMatchingRegistry } from "@spreadsheet/global_filters/helpers";
import { RelatedFilters } from "../related_filters/related_filters";

const { Section, SidePanelCollapsible } = components;
const { useStore, SidePanelStore } = stores;

export class RelatedFiltersSection extends Component {
    static template = "spreadsheet_edition.RelatedFiltersSection";
    static components = { SidePanelCollapsible, Section, RelatedFilters };
    static props = {
        resModel: String,
        dataSourceId: String,
        dataSourceType: String,
    };

    setup() {
        this.sidePanel = useStore(SidePanelStore);
    }

    get collapsibleTitle() {
        return _t("Matching %(matching)s / %(total)s filters", {
            matching: this.numberOfMatchingFilters,
            total: this.numberOfFilters,
        });
    }

    get numberOfFilters() {
        return this.env.model.getters.getGlobalFilters().length;
    }

    get numberOfMatchingFilters() {
        let count = 0;
        const matcher = globalFieldMatchingRegistry.get(this.props.dataSourceType);
        for (const filter of this.env.model.getters.getGlobalFilters()) {
            const fieldMatching = matcher.getFieldMatching(
                this.env.model.getters,
                this.props.dataSourceId,
                filter.id
            );
            if (fieldMatching?.chain) {
                count += 1;
            }
        }
        return count;
    }
}
