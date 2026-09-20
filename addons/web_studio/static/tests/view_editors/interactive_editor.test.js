import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { edit, press, waitFor } from "@odoo/hoot-dom";
import { animationFrame, Deferred } from "@odoo/hoot-mock";
import { onMounted } from "@odoo/owl";
import {
    contains,
    defineModels,
    editAce,
    editSelectMenu,
    fields,
    mockService,
    models,
    onRpc,
    patchWithCleanup,
    serverState,
    stepAllNetworkCalls,
} from "@web/../tests/web_test_helpers";
import { CodeEditor } from "@web/core/code_editor/code_editor";
import { editView, handleDefaultStudioRoutes, mountViewEditor } from "../view_editor_tests_utils";

describe.current.tags("desktop");

class Partner extends models.Model {
    _name = "partner";
}

defineMailModels();
defineModels([Partner]);
handleDefaultStudioRoutes();

test("add a monetary field without currency in the model", async () => {
    expect.assertions(3);
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].node.field_description).toEqual({
            field_description: "New Monetary",
            model_name: "partner",
            name: params.operations[0].node.field_description.name,
            type: "monetary",
        });

        Partner._fields.x_currency_id = fields.Many2one({
            string: "Currency",
            relation: "res.currency",
        });
        Partner._fields.monetary_field = fields.Monetary({
            currency_field: "x_currency_id",
        });
        const newArch =
            "<list><field name='display_name'/><field name='x_currency_id'/><field name='monetary_field'/></list>";
        return editView(params, "list", newArch);
    });

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='display_name'/></list>`,
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_monetary").dragAndDrop(
        "th.o_web_studio_hook"
    );
    expect.verifySteps(["edit_view"]);

    await contains("th[data-name='monetary_field']").click();
    expect(".o_web_studio_property_currency_field input").toHaveValue("Currency");
});

test("add a monetary field with currency in the model", async () => {
    expect.assertions(2);
    Partner._fields.x_currency_id = fields.Many2one({
        string: "Currency",
        relation: "res.currency",
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].node.field_description).toEqual({
            field_description: "New Monetary",
            model_name: "partner",
            name: params.operations[0].node.field_description.name,
            type: "monetary",
            currency_field: "x_currency_id",
            currency_in_view: false,
        });
    });

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='display_name'/></list>`,
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_monetary").dragAndDrop(
        "th.o_web_studio_hook"
    );
    expect.verifySteps(["edit_view"]);
});

test("add a monetary field with currency in the view", async () => {
    expect.assertions(2);
    Partner._fields.x_currency_id = fields.Many2one({
        string: "Currency",
        relation: "res.currency",
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].node.field_description).toEqual({
            field_description: "New Monetary",
            model_name: "partner",
            name: params.operations[0].node.field_description.name,
            type: "monetary",
            currency_field: "x_currency_id",
            currency_in_view: true,
        });
    });

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='display_name'/><field name='x_currency_id'/></list>`,
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_monetary").dragAndDrop(
        "th.o_web_studio_hook"
    );
    expect.verifySteps(["edit_view"]);
});

test("edit the currency of a monetary field", async () => {
    expect.assertions(3);
    Partner._fields.x_currency_id = fields.Many2one({
        string: "Currency",
        relation: "res.currency",
    });
    Partner._fields.x_currency_id2 = fields.Many2one({
        string: "Currency2",
        relation: "res.currency",
    });
    Partner._fields.monetary_field = fields.Monetary({
        currency_field: "x_currency_id",
        manual: true,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].node.attrs).toEqual({
            name: "x_currency_id2",
        });
    });

    onRpc("/web_studio/set_currency", async (request) => {
        const { params } = await request.json();
        expect.step("set_currency");
        expect(params).toEqual({
            model_name: "partner",
            field_name: "monetary_field",
            value: "x_currency_id2",
        });
        return true;
    });

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='display_name'/><field name='monetary_field'/><field name='x_currency_id'/></list>`,
    });

    await contains("th[data-name='monetary_field']").click();
    await editSelectMenu(".o_web_studio_sidebar .o_web_studio_property_currency_field input", {
        value: "Currency2",
    });
    expect.verifySteps(["set_currency", "edit_view"]);
});

test("field monetary not manual (base field) currency_field is readonly", async (assert) => {
    Partner._fields.x_currency_id = fields.Many2one({
        string: "Currency",
        relation: "res.currency",
    });

    Partner._fields.monetary_field = fields.Monetary({
        currency_field: "x_currency_id",
        manual: false,
    });
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: "<list><field name='display_name'/><field name='monetary_field'/><field name='x_currency_id'/></list>",
    });

    await contains("th[data-name='monetary_field']").click();
    await waitFor(".o_web_studio_sidebar input[name='currency_field']");
    expect(".o_web_studio_sidebar input[name='currency_field']:disabled").toHaveCount(1);
});

test("add a related field", async () => {
    expect.assertions(29);

    Partner._fields.pony_id = fields.Many2one({ relation: "pony" });

    class Pony extends models.Model {
        _name = "pony";

        m2o = fields.Many2one({ relation: "partner" });
        o2m = fields.One2many({ relation: "partner" });
        m2m = fields.Many2many({ relation: "partner" });
    }

    defineModels([Pony]);

    let nbEdit = 0;
    let arch = `<list><field name='display_name'/></list>`;
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        nbEdit++;
        expect.step("edit_view");
        if (nbEdit === 1) {
            expect(params.operations[0].node.field_description.related).toBe(
                "pony_id.display_name"
            );
            expect(params.operations[0].node.field_description.copy).toBe(false);
            expect(params.operations[0].node.field_description.readonly).toBe(true);
            expect(params.operations[0].node.field_description.store).toBe(false);
            Partner._fields.related_field = fields.Char({
                related: "pony_id.display_name",
            });
            arch = "<list><field name='display_name'/><field name='related_field'/></list>";
        } else if (nbEdit === 2) {
            expect(params.operations[1].node.field_description.related).toBe("pony_id.m2o");
            expect(params.operations[1].node.field_description.relation).toBe("partner");
            expect(params.operations[1].node.field_description.copy).toBe(false);
            expect(params.operations[1].node.field_description.readonly).toBe(true);
            expect(params.operations[1].node.field_description.store).toBe(false);
        } else if (nbEdit === 3) {
            expect(params.operations[2].node.field_description.related).toBe("pony_id.o2m");
            expect(params.operations[2].node.field_description.relational_model).toBe("pony");
            expect(params.operations[2].node.field_description.copy).toBe(false);
            expect(params.operations[2].node.field_description.readonly).toBe(true);
            expect(params.operations[2].node.field_description.store).toBe(false);
        } else if (nbEdit === 4) {
            expect(params.operations[3].node.field_description.related).toBe("pony_id.m2m");
            expect(params.operations[3].node.field_description.relation).toBe("partner");
            expect(params.operations[3].node.field_description.store).toBe(false);
        }

        return editView(params, "list", arch);
    });

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_related").dragAndDrop(
        ".o_web_studio_hook"
    );
    expect(".modal").toHaveCount(1);

    expect(".modal-footer .btn-primary").toHaveClass("disabled");
    await contains(".modal-footer .btn-primary").click();
    expect.verifySteps([]);

    expect(".modal").toHaveCount(1);

    await contains(".modal .o_model_field_selector").click();
    expect(".o_model_field_selector_popover li").toHaveCount(5);

    await contains(
        ".o_model_field_selector_popover li[data-name=pony_id] button.o_model_field_selector_popover_item_relation"
    ).click();
    await contains(".o_model_field_selector_popover li[data-name=display_name] button").click();
    await contains(".modal-footer .btn-primary").click();
    expect.verifySteps(["edit_view"]);

    await contains(".o_web_studio_sidebar .o_web_studio_new").click();
    await contains(".o_web_studio_new_fields .o_web_studio_field_related").dragAndDrop(
        ".o_web_studio_hook"
    );
    expect(".modal").toHaveCount(1);
    await contains(".modal .o_model_field_selector").click();
    await contains(
        ".o_model_field_selector_popover li[data-name=pony_id] button.o_model_field_selector_popover_item_relation"
    ).click();
    await contains(".o_model_field_selector_popover li[data-name=m2o] button").click();
    await contains(".modal-footer .btn-primary").click();
    expect.verifySteps(["edit_view"]);

    await contains(".o_web_studio_sidebar .o_web_studio_new").click();
    await contains(".o_web_studio_new_fields .o_web_studio_field_related").dragAndDrop(
        ".o_web_studio_hook"
    );
    expect(".modal").toHaveCount(1);
    await contains(".modal .o_model_field_selector").click();
    await contains(
        ".o_model_field_selector_popover li[data-name=pony_id] button.o_model_field_selector_popover_item_relation"
    ).click();
    await contains(".o_model_field_selector_popover li[data-name=o2m] button").click();
    await contains(".modal-footer .btn-primary").click();
    expect.verifySteps(["edit_view"]);

    await contains(".o_web_studio_sidebar .o_web_studio_new").click();
    await contains(".o_web_studio_new_fields .o_web_studio_field_related").dragAndDrop(
        ".o_web_studio_hook"
    );
    expect(".modal").toHaveCount(1);
    await contains(".modal .o_model_field_selector").click();
    await contains(
        ".o_model_field_selector_popover li[data-name=pony_id] button.o_model_field_selector_popover_item_relation"
    ).click();
    await contains(".o_model_field_selector_popover li[data-name=m2m] button").click();
    await contains(".modal-footer .btn-primary").click();
    expect.verifySteps(["edit_view"]);
});

test("add one2many field", async () => {
    expect.assertions(7);

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form><group>
                <field name="display_name"/>
            </group></form>`,
    });

    onRpc("ir.model.fields", "name_search", ({ kwargs }) => {
        expect(kwargs.domain).toEqual([
            "&",
            "&",
            "&",
            "&",
            ["relation", "=", "partner"],
            ["ttype", "=", "many2one"],
            ["model_id.abstract", "=", false],
            ["store", "=", true],
            "!",
            ["id", "in", []],
        ]);

        return [
            [1, "Field 1"],
            [2, "Field 2"],
        ];
    });

    onRpc("ir.model.fields", "search_count", ({ args }) => {
        expect.step("search_count ir.model.fields");
        expect(args).toEqual([
            [
                ["relation", "=", "partner"],
                ["ttype", "=", "many2one"],
                ["store", "=", true],
            ],
        ]);

        return 2;
    });

    onRpc("/web_studio/edit_view", () => expect.step("edit_view"));

    await contains(".o_web_studio_new_fields .o_web_studio_field_one2many").dragAndDrop(
        ".o_web_studio_hook"
    );
    expect(".modal").toHaveCount(1);
    expect.verifySteps(["search_count ir.model.fields"]);

    await contains(".modal button.btn-primary").click();
    expect(".modal").toHaveCount(1);

    await contains("div[name='relation_id'] input").click();
    await contains(".dropdown-item:contains('Field 1')").click();
    await contains(".modal button.btn-primary").click();
    expect(".modal").toHaveCount(0);
    expect.verifySteps(["edit_view"]);
});

test("add a one2many field without many2one", async () => {
    onRpc("ir.model.fields", "search_count", ({ args }) => {
        expect(args).toEqual([
            [
                ["relation", "=", "partner"],
                ["ttype", "=", "many2one"],
                ["store", "=", true],
            ],
        ]);

        return 0;
    });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form><group>
                <field name="display_name"/>
            </group></form>`,
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_one2many").dragAndDrop(
        ".o_web_studio_hook"
    );
    expect(".modal .modal-title").toHaveText("No related many2one fields found");

    await contains(".modal button.btn-primary").click();
    expect(".modal").toHaveCount(0);
});

test("add a one2many lines field", async () => {
    expect.assertions(2);
    onRpc("search_count", () => expect.step("should not do a search_count"));

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].node.field_description.special).toBe("lines");
    });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form><group>
                <field name="display_name"/>
            </group></form>`,
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_lines").dragAndDrop(
        ".o_web_studio_hook"
    );
    expect.verifySteps(["edit_view"]);
});

test("add a many2many field", async () => {
    expect.assertions(6);
    onRpc("name_search", () => [
        [1, "Model 1"],
        [2, "Model 2"],
    ]);

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        const fieldDescr = params.operations[0].node.field_description;
        expect(fieldDescr.name).toMatch(/^x_studio_many2many.*/);
        delete fieldDescr.name;
        expect(fieldDescr).toEqual({
            field_description: "New Many2Many",
            model_name: "partner",
            relation_id: 1,
            type: "many2many",
        });
    });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form><group>
                <field name="display_name"/>
            </group></form>`,
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_many2many").dragAndDrop(
        ".o_web_studio_hook"
    );
    expect(".modal").toHaveCount(1);

    await contains(".modal button.btn-primary").click();
    expect(".modal").toHaveCount(1);

    await contains("div[name='relation_id'] input").click();
    await contains(".dropdown-item:contains('Model 1')").click();
    await contains(".modal button.btn-primary").click();

    expect(".modal").toHaveCount(0);
    expect.verifySteps(["edit_view"]);
});

test("add a many2one field", async () => {
    expect.assertions(6);
    onRpc("name_search", () => [
        [1, "Model 1"],
        [2, "Model 2"],
    ]);

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        const fieldDescr = params.operations[0].node.field_description;
        expect(fieldDescr.name).toMatch(/^x_studio_many2one.*/);
        delete fieldDescr.name;
        expect(fieldDescr).toEqual({
            field_description: "New Many2One",
            model_name: "partner",
            relation_id: 1,
            type: "many2one",
        });
    });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form><group>
                <field name="display_name"/>
            </group></form>`,
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_many2one").dragAndDrop(
        ".o_web_studio_hook"
    );
    expect(".modal").toHaveCount(1);

    await contains(".modal button.btn-primary").click();
    expect(".modal").toHaveCount(1);

    await contains("div[name='relation_id'] input").click();
    await contains(".dropdown-item:contains('Model 1')").click();
    await contains(".modal button.btn-primary").click();

    expect(".modal").toHaveCount(0);
    expect.verifySteps(["edit_view"]);
});

test("switch mode after element removal", async () => {
    onRpc("/web_studio/edit_view", (request) => {
        expect.step("edit_view");
        const newArch = "<list><field name='display_name'/></list>";
        return editView(request, "list", newArch);
    });

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='id'/><field name='display_name'/></list>`,
    });

    expect(".o_web_studio_list_view_editor [data-studio-xpath]").toHaveCount(2);
    await contains(".o_web_studio_list_view_editor [data-studio-xpath]").click();
    expect(".o_web_studio_sidebar input[name='string']").toHaveValue("Id");

    await contains(".o_web_studio_sidebar .o_web_studio_remove").click();
    await contains(".modal button.btn-primary").click();
    expect.verifySteps(["edit_view"]);

    expect(".o_web_studio_list_view_editor [data-studio-xpath]").toHaveCount(1);
    expect(".o_web_studio_sidebar .nav-link.active").toHaveText("Add");
});

test("open XML editor in read-only", async () => {
    serverState.debug = "1";

    const def = new Deferred();
    patchWithCleanup(CodeEditor.prototype, {
        setup() {
            super.setup();
            onMounted(() => def.resolve());
        },
    });

    const arch = `<form><sheet><field name='display_name'/></sheet></form>`;
    onRpc("/web_studio/get_xml_editor_resources", async (request) => {
        const { params } = await request.json();
        expect.step("editor_resources");
        expect(params.key).toBe(99999999);
        return {
            views: [
                {
                    active: true,
                    arch: arch,
                    id: 99999999,
                    inherit_id: false,
                },
            ],
            scss: [],
            js: [],
        };
    });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch,
    });

    expect(
        ".o_web_studio_view_renderer .o_form_readonly.o_web_studio_form_view_editor"
    ).toHaveCount(1);
    await contains(".o_web_studio_sidebar .o_web_studio_view").click();

    expect(".o_web_studio_sidebar .o_web_studio_open_xml_editor").toHaveCount(1);

    await contains(".o_web_studio_sidebar .o_web_studio_open_xml_editor").click();
    await def;
    expect.verifySteps(["editor_resources"]);
    expect(
        ".o_web_studio_view_renderer .o_form_readonly:not(.o_web_studio_form_view_editor)"
    ).toHaveCount(1);
    expect(".o_web_studio_xml_editor .ace_editor").toHaveCount(1);
});

test("XML editor: reset operations stack", async () => {
    serverState.debug = "1";

    const def = new Deferred();
    patchWithCleanup(CodeEditor.prototype, {
        setup() {
            super.setup();
            onMounted(() => def.resolve());
        },
    });

    const arch = `<form><sheet><field name='display_name'/></sheet></form>`;
    onRpc("/web_studio/get_xml_editor_resources", async (request) => {
        const { params } = await request.json();
        expect(params.key).toBe(99999999);
        return {
            views: [
                {
                    active: true,
                    arch: arch,
                    id: 1,
                    inherit_id: false,
                    name: "base view",
                    key: 99999999,
                },
                {
                    active: true,
                    arch: "<data/>",
                    id: "__test_studio_view_arch__",
                    inherit_id: [1],
                    name: "studio view",
                },
            ],
            scss: [],
            js: [],
        };
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations).toHaveLength(1);
    });

    onRpc("/web_studio/edit_view_arch", async () => {
        expect.step("edit_view_arch");
        const result = await editView(
            { model: "partner", view_id: "__test_studio_view_arch__" },
            "form",
            arch
        );
        return { ...result, studio_view_id: "__test_studio_view_arch__" };
    });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch,
    });

    expect(
        ".o_web_studio_view_renderer .o_form_readonly.o_web_studio_form_view_editor"
    ).toHaveCount(1);
    await contains(".o_web_studio_form_view_editor .o_field_widget[name='display_name']").click();
    await contains(".o_web_studio_sidebar input[name='string']").click();
    await edit("Kikou");
    await press("Tab");
    await animationFrame();
    expect.verifySteps(["edit_view"]);

    await contains(".o_web_studio_sidebar .o_web_studio_view").click();
    expect(".o_web_studio_sidebar .o_web_studio_open_xml_editor").toHaveCount(1);
    await contains(".o_web_studio_sidebar .o_web_studio_open_xml_editor").click();

    await def;
    await editSelectMenu(".o_web_studio_xml_resource_select_menu .o_select_menu_toggler", {
        index: 1,
    });
    await editAce("<data/>");
    await animationFrame();

    await contains(".o_web_studio_xml_editor button.btn-primary").click();
    expect.verifySteps(["edit_view_arch"]);

    await contains(".o_web_studio_xml_editor button.btn-secondary").click();
    await contains(".o_web_studio_form_view_editor .o_field_widget[name='display_name']").click();
    await contains(".o_web_studio_sidebar input[name='string']").click();
    await edit("Kikou");
    await press("Tab");
    await animationFrame();

    expect.verifySteps(["edit_view"]);
});

test("blockUI not removed just after rename", async () => {
    serverState.debug = "1";
    stepAllNetworkCalls();

    mockService("ui", {
        block: () => expect.step("block"),
        unblock: () => expect.step("unblock"),
    });

    onRpc("/web_studio/edit_view", async (request) => {
        expect.step("edit_view");
        const { params } = await request.json();
        const fieldName = params.operations[0].node.field_description.name;
        const newArch = `<list><field name='${fieldName}'/><field name='display_name'/></list>`;
        Partner._fields[fieldName] = fields.Char();
        return editView(params, "list", newArch);
    });

    onRpc("/web_studio/rename_field", () => {
        expect.step("rename_field");
        return true;
    });

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: "<list><field name='display_name'/></list>",
    });

    expect.verifySteps([
        "/web/webclient/translations",
        "/web/webclient/load_menus",
        "get_views",
        "web_search_read",
        "has_group",
    ]);

    expect("thead th[data-studio-xpath]").toHaveCount(1);
    await contains(".o_web_studio_new_fields .o_web_studio_field_char").dragAndDrop(
        ".o_web_studio_hook"
    );
    await animationFrame();

    expect.verifySteps(["block", "edit_view", "web_search_read", "unblock"]);

    expect("thead th[data-studio-xpath]").toHaveCount(2);
    await contains(".o_web_studio_sidebar input[name='technical_name']").click();
    await edit("new");
    await press("Tab");
    await animationFrame();

    expect.verifySteps(["block", "rename_field", "edit_view", "web_search_read", "unblock"]);
});

test("arch classes are reflected in the DOM", async () => {
    await mountViewEditor({
        type: "kanban",
        resModel: "partner",
        arch: `
            <kanban class="my_custom_class my_custom_class2">
                <templates>
                    <t t-name='card'>
                        <field name='display_name'/>
                    </t>
                </templates>
            </kanban>`,
    });

    expect(".o_web_studio_view_renderer .o_view_controller").toHaveClass([
        "o_kanban_view",
        "my_custom_class",
        "my_custom_class2",
    ]);
});

test("edit selection values trims values", async () => {
    const arch = `<list><field name="display_name"/></list>`;
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].node.field_description.selection).toBe(
            '[["with spaces","with spaces"]]'
        );
        expect.step("edit_view");
    });

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_selection").dragAndDrop(
        ".o_web_studio_hook"
    );
    await contains(
        ".modal .o_web_studio_selection_editor .o-web-studio-interactive-list-item-input"
    ).edit("with spaces   ");
    await contains(".o-web-studio-interactive-list-edit-item").click();
    await contains(".modal .btn-primary").click();
    expect.verifySteps(["edit_view"]);
});
