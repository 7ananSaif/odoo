import * as spreadsheet from "@odoo/o-spreadsheet";

import { Component, onWillStart, onWillUnmount } from "@odoo/owl";
import { getFacetInfo } from "@spreadsheet/global_filters/helpers";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";
import { FilterValuesList } from "@spreadsheet/global_filters/components/filter_values_list/filter_values_list";
import { Dialog } from "@web/core/dialog/dialog";

const { Menu } = spreadsheet;

class FiltersTooltip extends Component {
    static template = "spreadsheet_edition.FiltersTooltip";
    static props = {
        model: Object,
        onMouseLeave: Function,
        onMouseEnter: Function,
        onClick: Function,
        close: { optional: true, type: Function },
    };
    static components = { Dialog };

    setup() {
        this.facets = [];
        this.nameService = useService("name");
        onWillStart(this.computeFacets.bind(this));
    }

    async computeFacets() {
        const filters = this.props.model.getters
            .getGlobalFilters()
            .filter((filter) => this.props.model.getters.isGlobalFilterActive(filter.id));
        this.facets = await Promise.all(filters.map((filter) => this.getFacetFor(filter)));
    }

    async getFacetFor(filter) {
        const filterValues = this.props.model.getters.getGlobalFilterValue(filter.id);
        return getFacetInfo(this.env, filter, filterValues);
    }
}

export class FilterValuesDialog extends Component {
    static template = "spreadsheet_edition.FilterValuesDialog";
    static components = { FilterValuesList, Dialog };
    static props = {
        close: Function,
        model: Object,
        openFiltersEditor: { type: Function, optional: true },
    };
}

export class FilterComponent extends Component {
    static template = "spreadsheet_edition.FilterComponent";
    static components = { Menu };
    static props = {};

    setup() {
        this.popover = usePopover(FiltersTooltip, { position: "bottom" });
        this.dialog = useService("dialog");

        onWillUnmount(() => {
            if (this.timeoutId) {
                clearTimeout(this.timeoutId);
            }
        });
    }

    onClickButton() {
        if (this.env.model.getters.getGlobalFilters().length) {
            this.openDialog();
        } else {
            this.env.toggleSidePanel("GLOBAL_FILTERS_SIDE_PANEL");
        }
    }

    openDialog() {
        const close = this.dialog.add(FilterValuesDialog, {
            model: this.env.model,
            openFiltersEditor: () => {
                this.env.toggleSidePanel("GLOBAL_FILTERS_SIDE_PANEL");
                close();
            },
        });
    }

    get activeFilter() {
        return this.env.model.getters.getActiveFilterCount();
    }

    openPopover(ev) {
        if (this.activeFilter) {
            this.popover.open(ev.currentTarget, {
                model: this.env.model,
                onMouseEnter: () => clearTimeout(this.timeoutId),
                onMouseLeave: this.closePopover.bind(this),
                onClick: this.openDialog.bind(this),
            });
        }
    }

    closePopover() {
        this.timeoutId = setTimeout(() => this.cleanupPopover(), 300);
    }

    cleanupPopover() {
        this.timeoutId = undefined;
        this.popover.close();
    }
}
