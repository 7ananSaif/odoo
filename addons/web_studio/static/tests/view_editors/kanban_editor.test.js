import { describe, expect, test } from "@odoo/hoot";
import { queryAllTexts } from "@odoo/hoot-dom";
import { animationFrame, Deferred } from "@odoo/hoot-mock";
import { onMounted } from "@odoo/owl";
import {
    contains,
    defineModels,
    fields,
    findComponent,
    models,
    onRpc,
    patchWithCleanup,
    serverState,
} from "@web/../tests/web_test_helpers";
import { CodeEditor } from "@web/core/code_editor/code_editor";

describe.current.tags("desktop");

import {
    disableHookAnimation,
    editView,
    mountViewEditor,
} from "@web_studio/../tests/view_editor_tests_utils";
import { KanbanEditorSidebar } from "@web_studio/client_action/view_editor/editors/kanban/kanban_editor_sidebar/kanban_editor_sidebar";

class Coucou extends models.Model {
    display_name = fields.Char();
    m2o = fields.Many2one({ relation: "product" });
    char_field = fields.Char();
    priority = fields.Selection({
        selection: [
            ["1", "Low"],
            ["2", "Medium"],
            ["3", "High"],
        ],
    });

    _records = [];
}

class Partner extends models.Model {
    display_name = fields.Char();
    image = fields.Binary();

    _records = [
        {
            id: 1,
            display_name: "jean",
        },
    ];
}

class Task extends models.Model {
    _name = "task";

    display_name = fields.Char({ sortable: false });
    int_field = fields.Integer();
    float_field = fields.Float();
    monetary_field = fields.Monetary({ currency_field: "" });
    _records = [
        {
            id: 1,
            int_field: 5,
            float_field: 19.99,
            monetary_field: 1.23,
        },
    ];
}

class User extends models.Model {
    _name = "res.users";
    has_group() {
        return true;
    }
}

class Product extends models.Model {
    display_name = fields.Char();

    _records = [{ id: 1, display_name: "A very good product" }];
}

defineModels([Coucou, Product, Partner, Task, User]);

test("empty kanban editor", async () => {
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban>
        <templates>
            <t t-name="card">
            </t>
        </templates>
    </kanban>
    `,
    });
    expect(".o_kanban_renderer").toHaveCount(1);
});

test("templates without a main node are wrapped in a main node by the editor", async () => {
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban>
        <templates>
            <t t-name="card">
                <field name="char_field"/>
            </t>
        </templates>
    </kanban>
    `,
    });
    expect("article.o_kanban_record > main").toHaveCount(1);
    expect("article.o_kanban_record > main").toHaveAttribute("studioxpath", null, {
        message: "no xpath is set on this element has it doesn't exist in the original template",
    });
    expect("article.o_kanban_record > .o_web_studio_hook[data-type=kanbanAsideHook]").toHaveCount(
        2,
        {
            message: "hooks are present around the element to drop an aside",
        }
    );
});

test("kanban structures display depends if element is present in the view", async () => {
    onRpc("/web_studio/edit_view", (request) => {
        // in this test, we result with a completely different template
        const newArch = `
                <kanban>
                    <templates>
                        <t t-name="card">
                            <widget name="web_ribbon" title="Ribbon"/>
                            <aside>
                            </aside>
                            <main>
                                <field name="char_field"/>
                            </main>
                        </t>
                    </templates>
                </kanban>
            `;
        return editView(request, "kanban", newArch);
    });
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban>
            <templates>
                <t t-name="card">
                    <field name="char_field"/>
                </t>
                <t t-name="menu">
                    <a>Item</a>
                </t>
            </templates>
        </kanban>
    `,
    });
    await contains(".o_web_studio_new").click();
    expect(".o_web_studio_field_menu").toHaveCount(0);
    expect(".o_web_studio_field_aside").toHaveCount(1);
    expect(".o_web_studio_field_footer").toHaveCount(1);
    expect(".o_web_studio_field_ribbon").toHaveCount(1);
    await contains(".o_web_studio_new_components .o_web_studio_field_aside").dragAndDrop(
        ".o_web_studio_hook[data-type=kanbanAsideHook]"
    );
    await contains(".o_web_studio_new").click();
    expect(".o_web_studio_field_menu").toHaveCount(1);
    expect(".o_web_studio_field_aside").toHaveCount(0);
    expect(".o_web_studio_field_footer").toHaveCount(1);
    expect(".o_web_studio_field_ribbon").toHaveCount(0);
});

test("hooks are placed inline around fields displayed in a span", async () => {
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban>
        <templates>
            <t t-name="card">
                <main>
                    <h3>Card</h3>
                    <div class="inline">
                        <field name="display_name"/>,
                        <field name="char_field"/>
                    </div>
                    <div class="block">
                        <field name="display_name" widget="char"/>,
                        <field name="char_field" widget="char"/>
                    </div>
                </main>
            </t>
        </templates>
    </kanban>
    `,
    });
    expect("article.o_kanban_record > main").toHaveCount(1);
    expect(".inline span.o_web_studio_hook[data-type=field]").toHaveCount(4, {
        message: "hooks are using a span instead of a div",
    });
    expect(".block div.o_web_studio_hook[data-type=field]").toHaveCount(4, {
        message: "hooks are using a div around field components",
    });
});

test("card without main should be able to add a footer", async () => {
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban>
        <templates>
            <t t-name="card">
                <h3>Card</h3>
                <div class="inline">
                    <field name="display_name"/>,
                    <field name="char_field"/>
                </div>
            </t>
        </templates>
    </kanban>
    `,
    });
    expect("main .o_web_studio_hook[data-structures=footer]").toHaveCount(1);
});

test("adding an aside element calls the right operation", async () => {
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].type).toBe("kanban_wrap_main");
        // server side, this operation would wrap the content inside a <main> node
        const newArch = `
                <kanban>
                    <templates>
                        <t t-name="card">
                            <main>
                                <t>
                                    <h3>Card</h3>
                                    <div class="inline">
                                        <field name="display_name"/>,
                                        <field name="char_field"/>
                                    </div>
                                </t>
                            </main>
                        </t>
                    </templates>
                </kanban>
            `;
        return editView(params, "kanban", newArch);
    });
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban>
        <templates>
            <t t-name="card">
                <h3>Card</h3>
            </t>
        </templates>
    </kanban>
    `,
    });
    await contains(".o_web_studio_new").click();
    await contains(".o_web_studio_new_components .o_web_studio_field_aside").dragAndDrop(
        ".o_web_studio_hook[data-type=kanbanAsideHook]"
    );
});

test("adding a footer element calls the right operation", async () => {
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].type).toBe("kanban_wrap_main");
        // server side, this operation would wrap the content inside a <main> node
        const newArch = `
                <kanban>
                    <templates>
                        <t t-name="card">
                            <main>
                                <t>
                                    <h3>Card</h3>
                                </t>
                            </main>
                        </t>
                    </templates>
                </kanban>
            `;
        return editView(params, "kanban", newArch);
    });
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban>
        <templates>
            <t t-name="card">
                <h3>Card</h3>
            </t>
        </templates>
    </kanban>
    `,
    });
    await contains(".o_web_studio_new").click();
    await contains(".o_web_studio_new_components .o_web_studio_field_footer").dragAndDrop(
        ".o_web_studio_hook[data-type=footer]"
    );
});

test("adding a menu element calls the right operation", async () => {
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].type).toBe("kanban_menu");
    });
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban>
        <templates>
            <t t-name="card">
                <h3>Card</h3>
            </t>
        </templates>
    </kanban>
    `,
    });
    disableHookAnimation();
    await contains(".o_web_studio_new").click();
    const { drop, moveTo } = await contains(
        ".o_web_studio_new_components .o_web_studio_field_menu"
    ).drag();
    await animationFrame();
    await moveTo(".o_web_studio_hook[data-type=t]");
    expect(".o_web_studio_hook[data-type=t]").toHaveClass("o_web_studio_hook_visible");
    await drop();
});

test("adding a colorpicker inside the menu", async () => {
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].type).toBe("kanban_colorpicker");

        Coucou._fields.x_color = fields.Integer({
            string: "Color",
        });
        const newArch = `
                    <kanban>
                        <templates>
                            <t t-name="card">
                                <h3>Card</h3>
                            </t>
                            <t t-name="menu">
                                <small>Menu</small>
                                <field name="x_color" widget="kanban_color_picker" />
                            </t>
                        </templates>
                    </kanban>
                `;
        return editView(params, "kanban", newArch);
    });
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban>
        <templates>
            <t t-name="card">
                <h3>Card</h3>
            </t>
            <t t-name="menu">
                <small>Menu</small>
            </t>
        </templates>
    </kanban>
    `,
    });
    disableHookAnimation();
    await contains(".o_web_studio_new").click();
    const { drop, moveTo } = await contains(
        ".o_web_studio_new_components .o_web_studio_field_color_picker"
    ).drag();
    await animationFrame();
    await moveTo(".o_web_studio_hook[data-type=t]");
    expect(".o_web_studio_hook[data-type=t]").toHaveClass("o_web_studio_hook_visible");
    await drop();
    expect(".o_dropdown_kanban").toHaveCount(1);
    await contains(".o_dropdown_kanban").click();
    expect(".o_notebook_content h3").toHaveText("Menu");
    await contains(".o_notebook_content .btn-secondary:contains(Color Picker)").click();
    expect(".o_notebook_content h3").toHaveText("Field", {
        message: "it is possible to edit the field with kanban_color_picker widget",
    });
});

test("adding a colorpicker when menu is not present", async () => {
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].type).toBe("kanban_menu");
        expect(params.operations[1].type).toBe("kanban_colorpicker");
        Coucou._fields.x_color = fields.Integer({
            string: "Color",
        });
        const newArch = `
                    <kanban>
                        <templates>
                            <t t-name="card">
                                <h3>Card</h3>
                            </t>
                            <t t-name="menu">
                                <field name="x_color" widget="kanban_color_picker" />
                            </t>
                        </templates>
                    </kanban>
                `;
        return editView(params, "kanban", newArch);
    });
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban>
        <templates>
            <t t-name="card">
                <h3>Card</h3>
            </t>
        </templates>
    </kanban>
    `,
    });
    disableHookAnimation();
    await contains(".o_web_studio_new").click();
    const { drop, moveTo } = await contains(
        ".o_web_studio_new_components .o_web_studio_field_color_picker"
    ).drag();
    await animationFrame();
    await moveTo(".o_web_studio_hook[data-type=t]");
    expect(".o_web_studio_hook[data-type=t]").toHaveClass("o_web_studio_hook_visible");
    await drop();
    expect(".o_dropdown_kanban").toHaveCount(1);
    await contains(".o_dropdown_kanban").click();
    expect(".o_notebook_content h3").toHaveText("Menu");
    await contains(".o_notebook_content .btn-secondary:contains(Color Picker)").click();
    expect(".o_notebook_content h3").toHaveText("Field", {
        message: "it is possible to edit the field with kanban_color_picker widget",
    });
});

test("can_open attribute can be edited from the sidebar", async () => {
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].new_attrs.can_open).toBe(false);
        const newArch = `
            <kanban can_open="false">
                <templates>
                    <t t-name="card">
                        <h3>Card</h3>
                    </t>
                </templates>
            </kanban>
        `;
        return editView(params, "kanban", newArch);
    });
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban>
        <templates>
            <t t-name="card">
                <h3>Card</h3>
            </t>
        </templates>
    </kanban>
    `,
    });
    await contains(".o_web_studio_view").click();
    expect("input[id=can_open]").toHaveCount(1);
    expect("input[id=can_open]").toBeChecked({
        message: "option is checked by default when the arch does not specify",
    });
    await contains("input[id=can_open]").click();
    expect("input[id=can_open]").not.toBeChecked();
});

test("buttons can be edited when being selected", async () => {
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban>
        <templates>
            <t t-name="card">
                <main>
                    Coucou
                    <footer>
                        <a type="action" name="my_first_action" class="btn btn-link" role="button">
                            <i class="fa fa-recycle"/> Do something
                        </a>
                        <button type="action" name="my_last_action" class="btn btn-primary" role="button">
                            Click me
                        </button>
                    </footer>
                </main>
            </t>
        </templates>
    </kanban>
    `,
    });
    onRpc("/web_studio/get_actions_for_model", () => [
        { name: "Action 1", xml_id: "my_first_action" },
        { name: "Action 2", xml_id: "my_last_action" },
    ]);
    expect("footer .o-web-studio-editor--element-clickable").toHaveCount(2);
    await contains("a.o-web-studio-editor--element-clickable").click();
    expect("input[id=class]").toHaveCount(1);
    expect("[name=name].o_select_menu_toggler").toHaveValue("Action 1");
    await contains("button.o-web-studio-editor--element-clickable").click();
    expect("input[id=class]").toHaveCount(1);
    expect("[name=name].o_select_menu_toggler").toHaveValue("Action 2");
});

test("grouped kanban editor", async () => {
    onRpc("web_read_group", ({ kwargs }) => {
        expect.step("web_read_group");
        expect(kwargs.limit).toBe(1);
    });
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban default_group_by='display_name'>
                    <templates>
                        <t t-name='card'>
                            <field name='display_name'/>
                        </t>
                    </templates>
                </kanban>`,
    });
    expect.verifySteps(["web_read_group"]);
    expect(".o_web_studio_kanban_view_editor").toHaveClass("o_kanban_grouped");
    expect(".o_web_studio_kanban_view_editor .o_view_nocontent").toHaveCount(0);
    expect(".o_web_studio_kanban_view_editor .o-web-studio-editor--element-clickable").toHaveCount(
        1
    );
    expect(".o_web_studio_kanban_view_editor .o-web-studio-editor--element-clickable").toHaveClass(
        "o_web_studio_widget_empty"
    );
    expect(".o_web_studio_kanban_view_editor .o_web_studio_hook").toHaveCount(7);
});

test("grouped kanban editor with record", async () => {
    Coucou._records = [{ id: 1, display_name: "coucou 1" }];
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban default_group_by='display_name'>
                    <templates>
                        <t t-name='card'>
                            <field name='display_name'/>
                        </t>
                    </templates>
                </kanban>`,
    });
    expect(".o_web_studio_kanban_view_editor").toHaveClass("o_kanban_grouped");
    expect(".o_kanban_group .o_kanban_header").toHaveCount(2);
    expect(".o_kanban_grouped .o_kanban_header_title").toHaveText("coucou 1\n(1)");
    expect(".o_kanban_group .o_kanban_counter").toHaveCount(0);
    expect(".o_web_studio_kanban_view_editor .o-web-studio-editor--element-clickable").toHaveCount(
        1
    );
    expect(
        ".o_web_studio_kanban_view_editor .o-web-studio-editor--element-clickable"
    ).not.toHaveClass("o_web_studio_widget_empty");
    expect(".o_web_studio_kanban_view_editor .o_web_studio_hook").toHaveCount(7);
});

test("kanban editor, grouped on date field, no record", async () => {
    Coucou._fields.date = fields.Date({ string: "Date" });
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban default_group_by='date'>
                <templates>
                    <t t-name='card'>
                        <field name='display_name'/>
                    </t>
                </templates>
            </kanban>`,
    });
    expect(".o_web_studio_kanban_view_editor").toHaveClass("o_kanban_grouped");
    expect(".o_kanban_record:not(.o_kanban_demo)").toHaveCount(1);
});

test("kanban editor, grouped on date field granular, no record, progressbar", async () => {
    Coucou._fields.date = fields.Date({ string: "Date" });
    serverState.debug = "1";
    const def = new Deferred();
    patchWithCleanup(CodeEditor.prototype, {
        setup() {
            super.setup();
            onMounted(() => def.resolve());
        },
    });
    const arch = `<kanban default_group_by='date:month'>
                <progressbar colors="{}" field="priority"/>
                <field name="priority" />
                <templates>
                    <t t-name='card'>
                        <field name='display_name'/>
                    </t>
                </templates>
            </kanban>`;
    onRpc("/web_studio/get_xml_editor_resources", () => ({
        main_view_key: "",
        views: [
            {
                active: true,
                arch,
                id: 99999999,
                inherit_id: false,
                name: "default view",
                xml_id: "default",
            },
        ],
    }));
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch,
    });
    expect(".o_web_studio_kanban_view_editor").toHaveClass("o_kanban_grouped");
    expect(".o_kanban_group .o_kanban_header").toHaveCount(2);
    expect(".o_kanban_grouped .o_kanban_header_title").toHaveText("Fake Group");
    expect(".o_kanban_group .o_kanban_counter").toHaveCount(2);
    expect(".o_kanban_record:not(.o_kanban_demo)").toHaveCount(1);
    await contains("button.o_web_studio_open_xml_editor").click();
    await def;
    expect(".o_web_studio_xml_editor").toHaveCount(1);
    expect(".o_view_controller.o_kanban_view").toHaveCount(1);
});

test("grouped kanban editor cannot add columns or load more", async () => {
    Coucou._records = [
        { id: 1, display_name: "Martin", priority: "2", m2o: 1 },
        { id: 2, display_name: "Jean", priority: "3", m2o: 1 },
    ];
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban default_group_by='m2o'>
                <templates>
                    <t t-name='card'>
                        <field name='display_name'/>
                    </t>
                </templates>
            </kanban>`,
    });
    expect(".o_kanban_load_more").toHaveCount(0);
    expect(".o_column_quick_create").toHaveCount(0);
});

test("kanban editor can group by only one field", async () => {
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban default_group_by='m2o,priority'>
                <templates>
                    <t t-name='card'>
                        <field name='display_name'/>
                    </t>
                </templates>
            </kanban>`,
    });
    expect(".o_web_studio_property_default_group_by .o_select_menu_toggler").toHaveValue("M2o");
});

test("grouped kanban fold_field can be change for custom model", async () => {
    expect.assertions(8);
    class CustomStage extends models.Model {
        _name = "x_custom_stage";

        boolean_field = fields.Boolean();
    }

    class Stage extends models.Model {
        _name = "stage";
    }

    class Lead extends models.Model {
        _name = "lead";

        stage_id = fields.Many2one({ relation: "stage" });
        custom_stage_id = fields.Many2one({ relation: "x_custom_stage" });
    }

    let nbEditView = 0;
    onRpc("/web_studio/edit_view", (request) => {
        nbEditView++;
        if (nbEditView === 1) {
            const newArch = `
                <kanban default_group_by="stage_id">
                    <templates>
                        <t t-name="card">
                            <h3>Card</h3>
                        </t>
                    </templates>
                </kanban>
            `;
            return editView(request, "kanban", newArch);
        } else if (nbEditView === 2) {
            const newArch = `
                <kanban default_group_by="custom_stage_id">
                    <templates>
                        <t t-name="card">
                            <h3>Card</h3>
                        </t>
                    </templates>
                </kanban>
            `;
            return editView(request, "kanban", newArch);
        }
    });

    onRpc("ir.model.fields", "web_search_read", () => []);

    onRpc("ir.model.fields", "write", ({ args }) => {
        expect(args[0][0]).toBe(999);
        expect(args[1]).toEqual({ group_expand: true });
        return true;
    });

    defineModels([CustomStage, Stage, Lead]);

    const parentComponent = await mountViewEditor({
        type: "kanban",
        resModel: "lead",
        arch: `
        <kanban>
            <templates>
                <t t-name="card">
                    <h3>Card</h3>
                </t>
            </templates>
        </kanban>
    `,
    });

    await contains(".o_web_studio_property_default_group_by input").click();
    await contains(".o-dropdown-item:contains('Stage')").click();

    expect("input[name='group_expand']").not.toHaveCount();
    expect(".o_web_studio_property_fold_name").not.toHaveCount();

    await contains(".o_web_studio_property_default_group_by input").click();
    await contains(".o-dropdown-item:contains('Custom stage')").click();

    expect("input[name='group_expand']").toBeVisible();
    expect(".o_web_studio_property_fold_name").not.toHaveCount();

    const kanbanEditor = findComponent(parentComponent, (c) => c instanceof KanbanEditorSidebar);
    kanbanEditor.state.groupByField = {
        id: 999,
    };

    kanbanEditor.state.fieldsForFold = [
        {
            label: "Folded1",
            value: 1,
        },
        {
            label: "Folded2",
            value: 2,
        },
    ];
    await contains("input[name='group_expand']").check();

    expect(".o_web_studio_property_fold_name").toBeVisible();

    await contains(".o_web_studio_property_fold_name input").click();
    expect(queryAllTexts(".o-dropdown-item")).toEqual(["Folded1", "Folded2"]);
});

test("sortby and orderby field in kanban sidebar", async () => {
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        const operation = params.operations[0];
        expect(operation.new_attrs.default_order).toBe("char_field asc");
        expect(operation.position).toBe("attributes");
        expect(operation.target.xpath_info).toEqual([{ tag: "kanban", indice: 1 }]);
        expect.step("edit_view");
        const newArch = `
            <kanban default_order="char_field asc">
                <templates>
                    <t t-name="card">
                        <h3>Card</h3>
                    </t>
                </templates>
            </kanban>
        `;
        return editView(params, "kanban", newArch);
    });
    await mountViewEditor({
        type: "kanban",
        resModel: "coucou",
        arch: `<kanban>
        <templates>
            <t t-name="card">
                <h3>Card</h3>
            </t>
        </templates>
    </kanban>
    `,
    });
    await contains(".o_web_studio_view").click();
    await contains(".o_web_studio_property_sort_by .o_select_menu .o_select_menu_toggler").click();
    await contains(".o-overlay-item:nth-child(1) .o-dropdown--menu .dropdown-item:eq(0)").click();
    expect(".o_web_studio_property_sort_by .o_select_menu input").toHaveValue("Char field");

    await contains(
        ".o_web_studio_property_sort_order .o_select_menu .o_select_menu_toggler"
    ).click();
    await contains(".o-overlay-item:nth-child(1) .o-dropdown--menu .dropdown-item:eq(0)").click();
    expect(".o_web_studio_property_sort_order .o_select_menu input").toHaveValue("Ascending");
    expect.verifySteps(["edit_view"]);
});

test("sortby numeric field in kanban sidebar", async () => {
    const arch = `
        <kanban>
            <templates>
                <t t-name='card'>
                    <field name='int_field'/>
                    <field name='float_field'/>
                </t>
            </templates>
        </kanban>`;

    await mountViewEditor({
        type: "kanban",
        resModel: "task",
        arch,
    });

    await contains(".o_web_studio_property_sort_by input").click();
    expect(queryAllTexts(".dropdown-item.o_select_menu_item")).toEqual([
        "Created on",
        "Float field",
        "Id",
        "Int field",
        "Last Modified on",
        "Monetary field",
    ]);
});
