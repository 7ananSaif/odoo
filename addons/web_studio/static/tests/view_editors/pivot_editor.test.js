import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { queryAllTexts } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    contains,
    defineModels,
    fields,
    getService,
    models,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { editView, handleDefaultStudioRoutes } from "../view_editor_tests_utils";

describe.current.tags("desktop");

defineMailModels();

class Partner extends models.Model {
    _name = "partner";

    name = fields.Char();

    _records = [{ name: "jean" }, { name: "jacques" }];
}

class Product extends models.Model {
    _name = "product";

    name = fields.Char();

    _records = [{ name: "xpad" }, { name: "xpod" }];
}

class Stage extends models.Model {
    _name = "stage";

    name = fields.Char({ groupable: true });
    partner_id = fields.Many2one({ relation: "partner", string: "partner_id" });
    product_id = fields.Many2one({ relation: "product", string: "product_id" });
    toughness = fields.Selection({
        selection: [
            ["0", "Hard"],
            ["1", "Harder"],
        ],
    });

    _records = [
        { name: "stage1", partner_id: 1, product_id: 1 },
        { name: "stage2", partner_id: 2, product_id: 2 },
    ];

    _views = {
        "pivot,1": `<pivot/>`,
        "pivot,2": `<pivot string='Pipeline Analysis'>
                <field name='product_id' type='col'/>
                <field name='partner_id' type='row'/>
            </pivot>`,
    };
}

defineModels([Stage, Partner, Product]);

handleDefaultStudioRoutes();

test("empty pivot editor", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        name: "Stage",
        res_model: "stage",
        type: "ir.actions.act_window",
        view_mode: "pivot",
        views: [
            [1, "pivot"],
            [false, "search"],
        ],
        group_ids: [],
    });

    await contains(".o_web_studio_navbar_item").click();

    expect(".o_pivot").toHaveCount(1);
    expect(".o_pivot > table").toHaveCount(1);
    expect(".o_web_studio_sidebar .nav-link.active").toHaveText("View");
});

test("switching column and row groupby fields in pivot editor", async () => {
    expect.assertions(20);

    let editViewCount = 0;

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        editViewCount++;
        if (editViewCount === 1) {
            expect(params.operations[0].target.field_names[0]).toBe("toughness");
            const arch = `
                <pivot>
                    <field name='product_id' type='col'/>
                    <field name='partner_id' type='row'/>
                    <field name='toughness' type='row'/>
                </pivot>`;
            return editView(params, "pivot", arch);
        } else if (editViewCount === 2) {
            expect(params.operations[1].target.field_names[0]).toBe("name");
            const arch = `
                <pivot string='Pipeline Analysis' colGroupBys='name' rowGroupBys='partner_id,toughness'>
                    <field name='name' type='col'/>
                    <field name='partner_id' type='row'/>
                    <field name='toughness' type='row'/>
                </pivot>`;
            return editView(params, "pivot", arch);
        } else if (editViewCount === 3) {
            expect(params.operations[2].target.field_names[0]).toBe("product_id");
            const arch = `
                <pivot string='Pipeline Analysis' colGroupBys='name' rowGroupBys='product_id'>
                    <field name='name' type='col'/>
                    <field name='product_id' type='row'/>
                </pivot>`;
            return editView(params, "pivot", arch);
        }
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        name: "Stage",
        res_model: "stage",
        type: "ir.actions.act_window",
        view_mode: "pivot",
        views: [
            [2, "pivot"],
            [false, "search"],
        ],
        group_ids: [],
    });

    await contains(".o_web_studio_navbar_item").click();

    expect(".o_web_studio_sidebar input[name='column_groupby']").toHaveValue("product_id");
    expect(".o_web_studio_sidebar input[name='first_row_groupby']").toHaveValue("partner_id");

    // set the Row-Second level field value
    await contains(".o_web_studio_sidebar input[name='second_row_groupby']").click();
    await contains(".o-dropdown-item:contains(Toughness)").click();

    expect.verifySteps(["edit_view"]);
    expect(".o_web_studio_sidebar input[name='column_groupby']").toHaveValue("product_id");
    expect(".o_web_studio_sidebar input[name='first_row_groupby']").toHaveValue("partner_id");
    expect(".o_web_studio_sidebar input[name='second_row_groupby']").toHaveValue("Toughness");
    expect(queryAllTexts(".o_web_studio_view_renderer th")).toEqual([
        "",
        "Total",
        "",
        "xpad",
        "xpod",
        "Count",
        "Count",
        "Count",
        "Total",
        "jean",
        "None",
        "jacques",
        "None",
    ]);

    // change the column field value to Name
    await contains(".o_web_studio_sidebar input[name='column_groupby']").click();
    await contains(".o-dropdown-item:contains(Name):not(:contains(Display))").click();

    expect.verifySteps(["edit_view"]);
    expect(".o_web_studio_sidebar input[name='column_groupby']").toHaveValue("Name");
    expect(".o_web_studio_sidebar input[name='first_row_groupby']").toHaveValue("partner_id");
    expect(".o_web_studio_sidebar input[name='second_row_groupby']").toHaveValue("Toughness");

    expect(queryAllTexts(".o_web_studio_view_renderer th")).toEqual([
        "",
        "Total",
        "",
        "stage1",
        "stage2",
        "Count",
        "Count",
        "Count",
        "Total",
        "jean",
        "None",
        "jacques",
        "None",
    ]);

    // change the Row-First level field value to product_id
    await contains(".o_web_studio_sidebar input[name='first_row_groupby']").click();
    await contains(".o-dropdown-item:contains(product_id)").click();

    expect.verifySteps(["edit_view"]);
    expect(".o_web_studio_sidebar input[name='column_groupby']").toHaveValue("Name");
    expect(".o_web_studio_sidebar input[name='first_row_groupby']").toHaveValue("product_id");
    expect(".o_web_studio_sidebar input[name='second_row_groupby']").toHaveValue("");

    expect(queryAllTexts(".o_web_studio_view_renderer th")).toEqual([
        "",
        "Total",
        "",
        "stage1",
        "stage2",
        "Count",
        "Count",
        "Count",
        "Total",
        "xpad",
        "xpod",
    ]);
});

test("pivot measure fields domain", async () => {
    expect.assertions(2);

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    onRpc("ir.model.fields", "name_search", (params) => {
        expect.step("name_search");
        expect(params.kwargs.domain).toEqual([
            "&",
            "&",
            ["model", "=", "stage"],
            ["name", "in", ["__count"]],
            "!",
            ["id", "in", []],
        ]);
    });

    await getService("action").doAction({
        name: "Stage",
        res_model: "stage",
        type: "ir.actions.act_window",
        view_mode: "pivot",
        views: [
            [1, "pivot"],
            [false, "search"],
        ],
        group_ids: [],
    });

    await contains(".o_web_studio_navbar_item").click();
    await contains(".o_field_many2many_tags input").click();
    expect.verifySteps(["name_search"]);
});
