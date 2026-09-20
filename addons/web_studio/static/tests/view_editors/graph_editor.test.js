import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { Deferred } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { onMounted } from "@odoo/owl";
import {
    contains,
    defineModels,
    fields,
    getService,
    models,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
    serverState,
} from "@web/../tests/web_test_helpers";
import { CodeEditor } from "@web/core/code_editor/code_editor";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { editView, handleDefaultStudioRoutes } from "../view_editor_tests_utils";

describe.current.tags("desktop");

defineMailModels();

class Stage extends models.Model {
    _name = "stage";

    name = fields.Char();
    char_field = fields.Char();

    _records = [{ name: "stage1" }, { name: "stage2" }];

    _views = {
        "graph,1": `<graph/>`,
    };
}

defineModels([Stage]);

handleDefaultStudioRoutes();

test("empty graph editor", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        name: "Stage",
        res_model: "stage",
        type: "ir.actions.act_window",
        view_mode: "graph",
        views: [
            [1, "graph"],
            [false, "search"],
        ],
        group_ids: [],
    });

    await contains(".o_web_studio_navbar_item").click();

    expect(".o_graph_view").toHaveCount(1);
    expect(".o_web_studio_view_renderer .o_graph_renderer").toHaveCount(1);
    expect(
        ".o_web_studio_view_renderer .o_graph_renderer .o_graph_canvas_container canvas"
    ).toHaveCount(1);
});

test("switching chart types in graph editor", async () => {
    let editViewCount = 0;

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        editViewCount++;
        if (editViewCount === 1) {
            expect.step(params.operations[0].new_attrs.type);
            const arch = `
                <graph string='Opportunities' type='line'>
                    <field name='name' type='col'/>
                    <field name='char_field' type='row'/>
                </graph>`;
            return editView(params, "graph", arch);
        } else if (editViewCount === 2) {
            expect.step(params.operations[1].new_attrs.type);
            const arch = `
                <graph string='Opportunities' type='pie'>
                    <field name='name' type='col'/>
                    <field name='char_field' type='row'/>
                </graph>`;
            return editView(params, "graph", arch);
        } else {
            const arch = `
                <graph string='Opportunities'>
                    <field name='name' type='col'/>
                    <field name='char_field' type='row'/>
                </graph>`;
            return editView(params, "graph", arch);
        }
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        name: "Stage",
        res_model: "stage",
        type: "ir.actions.act_window",
        view_mode: "graph",
        views: [
            [1, "graph"],
            [false, "search"],
        ],
        group_ids: [],
    });

    await contains(".o_web_studio_navbar_item").click();

    expect(".o_web_studio_sidebar .o_web_studio_property_type input").toHaveValue("Bar");
    expect("#stacked").toHaveCount(1);

    await contains(".o_web_studio_sidebar .o_web_studio_property_type input").click();
    await contains(".o-dropdown-item:contains(Line)").click();

    expect.verifySteps(["line"]);
    expect("#stacked").toHaveCount(0);

    await contains(".o_web_studio_sidebar .o_web_studio_property_type input").click();
    await contains(".o-dropdown-item:contains(Pie)").click();

    expect.verifySteps(["pie"]);
    expect("#stacked").toHaveCount(0);
});

test("open xml editor of graph component view and close it", async () => {
    serverState.debug = "1";

    // the XML editor lazy loads its libs and its templates so its start
    // method is monkey-patched to know when the widget has started
    const xmlEditorDef = new Deferred();

    patchWithCleanup(CodeEditor.prototype, {
        setup() {
            super.setup();
            onMounted(() => xmlEditorDef.resolve());
        },
    });

    onRpc("/web_studio/get_xml_editor_resources", () => ({
        views: [
            {
                active: true,
                arch: "<graph />",
                id: 1,
                inherit_id: false,
                name: "base view",
            },
            {
                active: true,
                arch: "<data/>",
                id: 42,
                inherit_id: 1,
                name: "studio view",
            },
        ],
        scss: [],
        js: [],
    }));

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        name: "Stage",
        res_model: "stage",
        type: "ir.actions.act_window",
        view_mode: "graph",
        views: [
            [1, "graph"],
            [false, "search"],
        ],
        group_ids: [],
    });

    await contains(".o_web_studio_navbar_item").click();
    await contains(".o_web_studio_editor .o_notebook_headers li:nth-child(2) a").click();
    await contains(".o_web_studio_open_xml_editor").click();
    await xmlEditorDef;

    expect(".o_web_studio_code_editor.ace_editor").toHaveCount(1);
    expect(".o_web_studio_xml_editor").toHaveCount(1);

    await contains(
        ".o_web_studio_xml_resource_selector .btn-secondary:not(.dropdown-toggle)"
    ).click();

    expect(".o_ace_view_editor").toHaveCount(0);
    expect(".o_web_studio_xml_editor").toHaveCount(0);
    expect(".o_graph_renderer").toHaveCount(1);
});
