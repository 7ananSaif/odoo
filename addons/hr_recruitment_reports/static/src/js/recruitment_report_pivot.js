import { pivotView } from "@web/views/pivot/pivot_view";
import { registry } from "@web/core/registry";
import { PivotRenderer } from "@web/views/pivot/pivot_renderer";

const viewRegistry = registry.category("views");

export class RecruitmentReportPivotRenderer extends PivotRenderer {
    /**
     * @param {CustomEvent} ev
     */
    onOpenView(cell) {
        if (cell.value === undefined || this.model.metaData.disableLinking) {
            return;
        }

        const context = Object.assign({}, this.model.searchParams.context);
        Object.keys(context).forEach((x) => {
            if (x === "group_by" || x.startsWith("search_default_")) {
                delete context[x];
            }
        });

        // retrieve form and list view ids from the action
        const { views = [] } = this.env.config;
        this.views = ["list", "form"].map((viewType) => {
            const view = views.find((view) => view[1] === viewType);
            return [view ? view[0] : false, viewType];
        });

        const group = { rowValues: cell.groupId[0], colValues: cell.groupId[1] };

        const domain = this.model.getGroupDomain(group);
        // Any measure that doesn't use a sum aggregator will never make sense
        // in a domain as you f.ex can't fetch a list of the the average
        // of a set of records.
        if (this.model.metaData.measures[cell.measure].aggregator === "sum") {
            domain.unshift("&");
            domain.push([cell.measure, "=", true]);
        }
        this.openView(domain, this.views, context);
    }
}

viewRegistry.add("recruitment_report_pivot", {
    ...pivotView,
    Renderer: RecruitmentReportPivotRenderer,
});
