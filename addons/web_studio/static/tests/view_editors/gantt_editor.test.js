import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { queryAllTexts } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    contains,
    defineModels,
    editSelectMenu,
    fields,
    getService,
    models,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { handleDefaultStudioRoutes } from "../view_editor_tests_utils";

describe.current.tags("desktop");

defineMailModels();

class Timeshift extends models.Model {
    _name = "timeshift";

    start = fields.Datetime();
    stop = fields.Datetime();

    _records = [
        {
            start: "2018-11-30 18:30:00",
            stop: "2018-12-31 18:29:59",
        },
    ];

    _views = {
        "gantt,1": `<gantt date_start='start' date_stop='stop' />`,
        "gantt,2": `<gantt date_start='start' date_stop='stop' scales="day,month"/>`,
    };
}

defineModels([Timeshift]);

handleDefaultStudioRoutes();

test("empty gantt editor", async () => {
    expect.assertions(3);

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].new_attrs.precision).toBe(`{"day":"hour:quarter"}`);
        return true;
    });

    await getService("action").doAction({
        name: "Timeshift",
        res_model: "timeshift",
        type: "ir.actions.act_window",
        view_mode: "gantt",
        views: [
            [1, "gantt"],
            [false, "search"],
        ],
        group_ids: [],
    });

    await contains(".o_web_studio_navbar_item").click();

    expect(".o_web_studio_view_renderer .o_gantt_renderer").toHaveCount(1);
    expect(".o_web_studio_sidebar .o_web_studio_property_precision_day .o_select_menu").toHaveCount(
        1
    );
    await editSelectMenu(".o_web_studio_property_precision_day input", { value: "Quarter Hour" });
});

test("only show allowed scales as default scale", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        name: "Timeshift",
        res_model: "timeshift",
        type: "ir.actions.act_window",
        view_mode: "gantt",
        views: [
            [2, "gantt"],
            [false, "search"],
        ],
        group_ids: [],
    });

    await contains(".o_web_studio_navbar_item").click();
    await contains(".o_web_studio_property_default_range .dropdown-toggle").click();
    expect(queryAllTexts(".o_select_menu_menu .dropdown-item")).toEqual(["Day", "Month"]);
});
