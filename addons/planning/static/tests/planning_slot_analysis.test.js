import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";

import { WebClient } from "@web/webclient/webclient";
import { clickOnDataset, setupChartJsForTests } from "@web/../tests/views/graph/graph_test_helpers";
import {
    contains,
    fields,
    getService,
    mockService,
    models,
    mountWithCleanup,
} from "@web/../tests/web_test_helpers";

import { definePlanningModels, planningModels } from "./planning_mock_models";

describe.current.tags("desktop");

class PlanningAnalysisReport extends models.Model {
    _name = "planning.analysis.report";

    slot_id = fields.Many2one({ relation: "planning.slot" });

    _records = [
        { id: 1, slot_id: 1 },
        { id: 2, slot_id: 1 },
        { id: 3, slot_id: 2 },
    ];

    _views = {
        "graph,false": `
            <graph string="Planning Analysis" sample="1" js_class="planning_slot_analysis_graph">
                <field name="slot_id"/>
            </graph>
        `,
        "pivot,false": `
            <pivot string="Planning Analysis" display_quantity="1" sample="1" js_class="planning_slot_analysis_pivot">
                <field name="slot_id"/>
            </pivot>
        `,
        "search,false": `<search/>`,
    };
}

beforeEach(() => {
    planningModels.PlanningSlot._records = [
        {
            id: 1,
            name: "test",
            start_datetime: "2022-10-09 00:00:00",
            end_datetime: "2022-10-16 22:00:00",
        },
        {
            id: 2,
            name: "test 2",
            start_datetime: "2022-11-09 00:00:00",
            end_datetime: "2022-11-16 22:00:00",
        },
    ];
    planningModels.PlanningSlot._views = {
        "form,false": `<form><field name="name"/></form>`,
        "list,false": `<list><field name="name"/></list>`,
        "search,false": `<search><field name="name"/></search>`,
    };
    planningModels.PlanningAnalysisReport = PlanningAnalysisReport;
    definePlanningModels();

    mockService("action", {
        doAction({ res_model }) {
            expect.step(res_model);
            return super.doAction(...arguments);
        },
    });
});

// Helper utility method to mount a WebClient and a specific view.
async function mountView(viewName) {
    const view = await mountWithCleanup(WebClient);
    await getService("action").doAction({
        id: 1,
        name: "planning analysis",
        res_model: "planning.analysis.report",
        type: "ir.actions.act_window",
        views: [[false, viewName]],
    });
    return view;
}

setupChartJsForTests();

test("planning.analysis.report (graph): clicking on a bar leads to planning.slot list", async () => {
    const view = await mountView("graph");
    await animationFrame();
    await clickOnDataset(view);
    await animationFrame();

    expect(".o_list_renderer").toBeDisplayed({ message: "Clicking on a bar should open a list view" });
    expect.verifySteps(["planning.analysis.report", "planning.slot"]);
});

test("planning.analysis.report (pivot): clicking on a cell leads to planning.slot list", async () => {
    await mountView("pivot");
    await animationFrame();
    await contains(".o_pivot_cell_value").click();
    await animationFrame();

    expect(".o_list_renderer").toBeDisplayed({ message: "Clicking on a cell should open a list view" });
    expect.verifySteps(["planning.analysis.report", "planning.slot"]);
});
