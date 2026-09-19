import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { edit, press, queryAllTexts } from "@odoo/hoot-dom";
import { advanceTime, animationFrame } from "@odoo/hoot-mock";
import { onWillRender } from "@odoo/owl";
import {
    contains,
    defineModels,
    editSelectMenu,
    fields,
    getService,
    MockServer,
    mockService,
    models,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
    serverState,
} from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";
import { ListRenderer } from "@web/views/list/list_renderer";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { ListEditorRenderer } from "@web_studio/client_action/view_editor/editors/list/list_editor_renderer";
import { SIDEBAR_SAFE_FIELDS } from "@web_studio/client_action/view_editor/editors/sidebar_safe_fields";
import { editView, handleDefaultStudioRoutes, mountViewEditor } from "../view_editor_tests_utils";

describe.current.tags("desktop");

class Partner extends models.Model {
    _name = "partner";
}

defineModels([Partner]);

defineMailModels();

test("list editor sidebar", async () => {
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list/>`,
    });

    expect(".o_web_studio_sidebar").toHaveCount(1);
    expect(".o_web_studio_sidebar .nav-link.active").toHaveClass(["o_web_studio_new"]);
    expect(".o_web_studio_sidebar .tab-pane h3").toHaveCount(2);
    expect(".nav-tabs > li:has(> .o_web_studio_properties)").toHaveClass(["disabled"]);

    await contains(".o_web_studio_view").click();
    expect(".o_web_studio_sidebar .nav-link.active").toHaveClass(["o_web_studio_view"]);
});

test("empty list editor", async () => {
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list/>`,
    });

    expect(".o_web_studio_list_view_editor").toHaveCount(1);
    expect(".o_web_studio_list_view_editor table thead th.o_web_studio_hook").toHaveCount(1);
    expect(".o_web_studio_list_view_editor [data-studio-xpath]").toHaveCount(0);

    await contains(".o_web_studio_existing_fields_header").click();
    expect(
        ".o_web_studio_sidebar .o_web_studio_existing_fields .o_web_studio_component"
    ).toHaveCount(Object.keys(Partner._fields).length);
});

test("search existing fields into sidebar", async () => {
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list/>`,
    });

    await contains(".o_web_studio_existing_fields_header").click();
    expect(
        ".o_web_studio_sidebar .o_web_studio_existing_fields .o_web_studio_component"
    ).toHaveCount(Object.keys(Partner._fields).length);
    await contains(".o_web_studio_sidebar_search_input").click();
    await edit("id");
    await animationFrame();
    expect(
        ".o_web_studio_sidebar .o_web_studio_existing_fields .o_web_studio_component"
    ).toHaveCount(1);
    await edit("coucou");
    await animationFrame();
    expect(
        ".o_web_studio_sidebar .o_web_studio_existing_fields .o_web_studio_component"
    ).toHaveCount(0);
});

test("list editor", async () => {
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='display_name'/></list>`,
    });

    expect(".o_web_studio_list_view_editor table thead [data-studio-xpath]").toHaveCount(1);
    expect("table thead th.o_web_studio_hook").toHaveCount(2);

    await contains(".o_web_studio_existing_fields_header").click();
    expect(
        ".o_web_studio_sidebar .o_web_studio_existing_fields .o_web_studio_component"
    ).toHaveCount(Object.keys(Partner._fields).length - 1);

    expect("thead th").toHaveCount(3);
    expect("tbody tr").toHaveCount(4);
    expect("tbody td.o_data_cell").toHaveCount(MockServer.env["partner"].length);
    expect("tbody tr:not(.o_data_row) td").toHaveAttribute("colspan", "3");
    expect("tfoot td").toHaveCount(1);
});

test("disable optional field dropdown icon", async () => {
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='display_name' optional='show'/></list>`,
    });

    expect("i.o_optional_columns_dropdown_toggle").toHaveCount(1);
    expect("i.o_optional_columns_dropdown_toggle").toHaveClass(["text-muted"]);
    await contains("i.o_optional_columns_dropdown_toggle").click();
    expect(".o-dropdown--menu").toHaveCount(0);
});

test("optional field in list editor", async () => {
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='display_name'/></list>`,
    });

    await contains(".o_web_studio_view_renderer [data-studio-xpath").click();
    expect(".o_web_studio_sidebar .o_web_studio_property_optional").toHaveCount(1);
});

test("new field should come with 'show' as default value of optional", async () => {
    expect.assertions(1);
    const arch = `<list><field name='display_name'/></list>`;

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].node.attrs.optional).toBe("show");
        return editView(params, "list", arch);
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_char").dragAndDrop(
        ".o_web_studio_hook"
    );
});

test("new field before a button_group", async () => {
    expect.assertions(3);
    const arch = `
        <list>
            <button name="action_1" type="object"/>
            <button name="action_2" type="object"/>
            <field name='display_name'/>
        </list>
    `;

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].type).toBe("add");
        expect(params.operations[0].position).toBe("before");
        expect(params.operations[0].target).toEqual({
            tag: "button",
            attrs: {
                name: "action_1",
            },
            xpath_info: [
                {
                    tag: "list",
                    indice: 1,
                },
                {
                    tag: "button",
                    indice: 1,
                },
            ],
        });
        return editView(params, "list", arch);
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_char").dragAndDrop(
        ".o_web_studio_hook"
    );
    await advanceTime(4000);
});

test("new field after a button_group", async () => {
    expect.assertions(3);
    const arch = `
        <list>
            <field name='display_name'/>
            <button name="action_1" type="object"/>
            <button name="action_2" type="object"/>
        </list>
    `;

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].type).toBe("add");
        expect(params.operations[0].position).toBe("after");
        expect(params.operations[0].target).toEqual({
            tag: "button",
            attrs: {
                name: "action_2",
            },
            xpath_info: [
                {
                    tag: "list",
                    indice: 1,
                },
                {
                    tag: "button",
                    indice: 2,
                },
            ],
        });
        return editView(params, "list", arch);
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_char").dragAndDrop(
        ".o_web_studio_hook:nth-child(5)"
    );
    await advanceTime(4000);
});

test("prevent click on button", async () => {
    Partner._records = [{ id: 1 }];
    mockService("action", {
        doAction() {
            expect.step("doAction");
        },
        doActionButton() {
            expect.step("doActionButton");
        },
    });

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `
            <list>
                <field name='display_name'/>
                <button name="action_1" type="object"/>
            </list>
        `,
    });

    await contains(".o_data_cell button").click();
    expect.verifySteps([]);
});

test("invisible field in list editor", async () => {
    Partner._records = [{ id: 1 }];
    const arch = `<list><field invisible="1" name="display_name"/></list>`;

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    await contains(".o_web_studio_view").click();
    await contains("#show_invisible").click();
    expect("td[name='display_name'].o_web_studio_show_invisible").toHaveCount(1);

    await contains("tr:first-child td[name='display_name'].o_web_studio_show_invisible").click();
    expect("#invisible").toHaveCount(1);
    expect("#invisible").toBeChecked();
});

test("column invisible field in list editor", async () => {
    Partner._records = [{ id: 1 }];
    const arch = `<list><field column_invisible="1" name="display_name"/></list>`;

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    await contains(".o_web_studio_view").click();
    await contains("#show_invisible").click();
    expect("td[name='display_name'].o_web_studio_show_invisible").toHaveCount(1);

    await contains("tr:first-child td[name='display_name'].o_web_studio_show_invisible").click();
    expect("#invisible").toBeChecked();
});

test("invisible toggle field in list editor", async () => {
    expect.assertions(2);
    const operations = [
        {
            type: "attributes",
            target: {
                tag: "field",
                attrs: {
                    name: "display_name",
                },
                xpath_info: [
                    {
                        tag: "list",
                        indice: 1,
                    },
                    {
                        tag: "field",
                        indice: 1,
                    },
                ],
            },
            position: "attributes",
            new_attrs: {
                column_invisible: "False",
                invisible: "False",
            },
        },
    ];

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field column_invisible="1" name="display_name"/></list>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations).toEqual(operations);
        const arch = `<list><field name="display_name"/></list>`;
        return editView(params, "list", arch);
    });

    await contains(".o_web_studio_view").click();
    await contains("#show_invisible").click();
    await contains("th[data-name='display_name'].o_web_studio_show_invisible").click();
    await contains("#invisible").click();

    expect("#invisible").not.toBeChecked();
});

test("field widgets correctly displayed and whitelisted in the sidebar (debug=false)", async () => {
    const wowlFieldRegistry = registry.category("fields");
    const charField = wowlFieldRegistry.get("char");
    // Clean registry to avoid having noise from all the other widgets
    wowlFieldRegistry.getEntries().forEach(([key]) => {
        wowlFieldRegistry.remove(key);
    });

    class SafeWidget extends charField.component {}
    wowlFieldRegistry.add("safeWidget", {
        ...charField,
        component: SafeWidget,
        displayName: "Test Widget",
    });
    SIDEBAR_SAFE_FIELDS.push("safeWidget");

    class SafeWidgetNoDisplayName extends charField.component {}
    const safeWidgetNoDisplayName = {
        ...charField,
        component: SafeWidgetNoDisplayName,
    };
    delete safeWidgetNoDisplayName.displayName;

    class UnsafeWidget extends charField.component {}
    wowlFieldRegistry.add("unsafeWidget", {
        ...charField,
        component: UnsafeWidget,
    });
    wowlFieldRegistry.add("safeWidgetNoDisplayName", safeWidgetNoDisplayName);
    SIDEBAR_SAFE_FIELDS.push("safeWidgetNoDisplayName");

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name="display_name"/></list>`,
    });

    await contains("thead th[data-studio-xpath]").click();
    await contains(".o_web_studio_property_widget .o_select_menu_toggler").click();
    expect(queryAllTexts(".o_select_menu_menu .o_select_menu_item")).toEqual([
        "(safeWidgetNoDisplayName)",
        "Test Widget (safeWidget)",
    ]);
});

test("field widgets correctly displayed and whitelisted in the sidebar (debug=true)", async () => {
    serverState.debug = "1";

    const wowlFieldRegistry = registry.category("fields");
    const charField = wowlFieldRegistry.get("char");
    // Clean registry to avoid having noise from all the other widgets
    wowlFieldRegistry.getEntries().forEach(([key]) => {
        wowlFieldRegistry.remove(key);
    });

    class SafeWidget extends charField.component {}
    wowlFieldRegistry.add("safeWidget", {
        ...charField,
        component: SafeWidget,
        displayName: "Test Widget",
    });
    SIDEBAR_SAFE_FIELDS.push("safeWidget");

    class SafeWidgetNoDisplayName extends charField.component {}
    const safeWidgetNoDisplayName = {
        ...charField,
        component: SafeWidgetNoDisplayName,
    };
    delete safeWidgetNoDisplayName.displayName;

    class UnsafeWidget extends charField.component {}
    wowlFieldRegistry.add("unsafeWidget", {
        ...charField,
        component: UnsafeWidget,
    });
    wowlFieldRegistry.add("safeWidgetNoDisplayName", safeWidgetNoDisplayName);
    SIDEBAR_SAFE_FIELDS.push("safeWidgetNoDisplayName");

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name="display_name"/></list>`,
    });

    await contains("thead th[data-studio-xpath]").click();
    await contains(".o_web_studio_property_widget .o_select_menu_toggler").click();
    expect(queryAllTexts(".o_select_menu_menu .o_select_menu_item")).toEqual([
        "(safeWidgetNoDisplayName)",
        "Test Widget (safeWidget)",
        "Text (unsafeWidget)",
    ]);
});

test("visible studio hooks in listview", async () => {
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name="display_name"/></list>`,
    });

    onRpc("/web_studio/edit_view", (request) => {
        const arch = `
            <list editable='bottom'>
                <field name='display_name'/>
            </list>`;
        return editView(request, "list", arch);
    });

    expect("th.o_web_studio_hook").toBeVisible();

    await contains(".o_web_studio_view").click();
    await animationFrame();
    await editSelectMenu(".o_web_studio_sidebar .o_web_studio_property_editable input", {
        value: "Add record at the bottom",
    });

    expect("th.o_web_studio_hook").toBeVisible();
});

test("sortby and orderby field in sidebar", async () => {
    let editViewCount = 0;

    Partner._fields.char_field = fields.Char({ string: "char_field" });
    Partner._fields.display_name.store = true;

    const arch = `
        <list default_order='char_field desc, display_name asc'>
            <field name='display_name'/>
                    <field name='char_field'/>
        </list>`;

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    onRpc("/web_studio/edit_view", (request) => {
        editViewCount++;
        let newArch = arch;
        if (editViewCount === 1) {
            newArch = `
                <list default_order='display_name asc'>
                    <field name='display_name'/>
                    <field name='char_field'/>
                </list>`;
        } else if (editViewCount === 2) {
            newArch = `
                <list default_order='display_name desc'>
                    <field name='display_name'/>
                    <field name='char_field'/>
                </list>`;
        } else if (editViewCount === 3) {
            newArch = `
                <list>
                    <field name='display_name'/>
                    <field name='char_field'/>
                </list>`;
        }
        return editView(request, "list", newArch);
    });

    await contains(".o_web_studio_view").click();
    await animationFrame();
    expect(".o_web_studio_property_sort_by .o_select_menu").toHaveCount(1);
    expect(".o_web_studio_property_sort_by .o_select_menu input").toHaveValue("char_field");

    expect(".o_web_studio_property_sort_order .o_select_menu input").toHaveValue("Descending");
    await editSelectMenu(".o_web_studio_property_sort_by input", { value: "Display name" });

    expect(".o_web_studio_property_sort_order .o_select_menu input").toHaveValue("Ascending");
    expect(".o_web_studio_property_sort_order").toHaveCount(1);
    await editSelectMenu(".o_web_studio_property_sort_order input", { value: "Descending" });

    expect(".o_web_studio_property_sort_order .o_select_menu input").toHaveValue("Descending");
    await editSelectMenu(".o_web_studio_property_sort_by input", { value: "" });
    expect(".o_web_studio_property_sort_order").toHaveCount(0);
});

test("many2many, one2many, binary fields and non-stored fields cannot be selected in SortBy dropdown for list editor", async () => {
    Partner._fields.char_field = fields.Char();
    Partner._fields.m2o_field = fields.Many2one({ relation: "res.users" });
    Partner._fields.o2m_field = fields.One2many({ relation: "res.users" });
    Partner._fields.m2m_field = fields.Many2many({ relation: "res.users" });
    Partner._fields.binary_field = fields.Binary();
    Partner._fields.id.store = true;

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `
            <list>
                <field name="id"/>
                <field name="display_name"/>
                <field name="m2o_field"/>
                <field name="o2m_field"/>
                <field name="m2m_field"/>
                <field name="binary_field"/>
                <field name="char_field"/>
            </list>
        `,
    });

    await contains(".o_web_studio_view").click();
    expect("th[data-name='display_name']").toHaveCount(1);
    expect("th[data-name='o2m_field']").toHaveCount(1);
    expect("th[data-name='m2m_field']").toHaveCount(1);
    expect("th[data-name='binary_field']").toHaveCount(1);

    await contains(".o_web_studio_property_sort_by input").click();
    expect(queryAllTexts(".dropdown-item.o_select_menu_item")).toEqual([
        "Char field",
        "Id",
        "M2o field",
    ]);
});

test("already selected unsafe widget without description property should be shown in sidebar with its technical name", async () => {
    const wowlFieldRegistry = registry.category("fields");
    const charField = wowlFieldRegistry.get("char");
    class WidgetWithoutDescription extends charField.component {}
    const widgetWithoutDescription = {
        ...charField,
        component: WidgetWithoutDescription,
    };
    delete widgetWithoutDescription.displayName;
    wowlFieldRegistry.add("widgetWithoutDescription", widgetWithoutDescription);

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='display_name' widget='widgetWithoutDescription'/></list>`,
    });

    await contains("thead th[data-studio-xpath]").click();
    expect(".o_web_studio_property_widget input").toHaveValue("(widgetWithoutDescription)");
});

test("already selected widget wihtout supportingTypes should be shown in sidebar with its technical name", async () => {
    const wowlFieldRegistry = registry.category("fields");
    const charField = wowlFieldRegistry.get("char");
    class WidgetWithoutTypes extends charField.component {}
    const widgetWithoutTypes = {
        ...charField,
        component: WidgetWithoutTypes,
    };
    delete widgetWithoutTypes.displayName;
    delete widgetWithoutTypes.supportedTypes;
    wowlFieldRegistry.add("widgetWithoutTypes", widgetWithoutTypes);

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='display_name' widget='widgetWithoutTypes'/></list>`,
    });

    await contains("thead th[data-studio-xpath]").click();
    expect(".o_web_studio_property_widget input").toHaveValue("(widgetWithoutTypes)");
});

test("editing selection field of list of form view", async () => {
    expect.assertions(3);
    class Product extends models.Model {
        _name = "product";

        toughness = fields.Selection({
            selection: [
                ["0", "Hard"],
                ["1", "Harder"],
            ],
            manual: true,
        });
    }

    defineModels([Product]);
    Partner._fields.product_ids = fields.One2many({ relation: "product" });

    const arch = `
        <form>
            <group>
                <field name="product_ids"><list>
                    <field name="toughness"/>
                </list></field>
            </group>
        </form>`;

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch,
    });

    onRpc("/web_studio/edit_field", async (request) => {
        const { params } = await request.json();
        expect(params.model_name).toBe("product");
        expect(params.field_name).toBe("toughness");
        expect(params.values).toEqual({
            selection: '[["0","Hard"],["1","Harder"],["Hardest","Hardest"]]',
        });
    });

    await contains(".o_field_one2many").click();
    await contains("button.o_web_studio_editX2Many[data-type='list']").click();
    await contains("th[data-studio-xpath]").click();
    await contains(".o_web_studio_edit_selection_values").click();
    await contains(".o-web-studio-interactive-list-item-input").edit("Hardest");
    await contains(".o_web_studio_add_selection button").click();
    await contains(".modal .btn-primary").click();
});

test("deleting selection field value which is linked in other records", async () => {
    expect.assertions(8);

    Partner._fields.priority = fields.Selection({
        selection: [
            ["1", "Low"],
            ["2", "Medium"],
            ["3", "High"],
        ],
        manual: true,
    });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form>
            <group>
                <field name="priority"/>
            </group>
        </form>`,
    });

    let nbEdit = 0;
    onRpc("/web_studio/edit_field", async (request) => {
        const { params } = await request.json();
        nbEdit++;
        if (nbEdit === 1) {
            expect(params.force_edit).toBe(false);
            expect(params.values).toEqual({
                selection: '[["1","Low"],["2","Medium"]]',
            });
            return Promise.resolve({
                records_linked: 3,
                message: "There are 3 records linked, upon confirming records will be deleted.",
            });
        } else if (nbEdit === 2) {
            expect(params.force_edit).toBe(true);
            expect(params.values).toEqual({
                selection: '[["1","Low"],["2","Medium"]]',
            });
        }
    });

    await contains(".o_form_label").click();
    await contains(".o_web_studio_edit_selection_values").click();
    expect(".modal .o_web_studio_selection_editor > li").toHaveCount(3);

    await contains(".o_web_studio_selection_editor > li:nth-child(3) .fa-trash-o").click();
    expect(".modal .o_web_studio_selection_editor > li").toHaveCount(2);

    await contains(".modal .btn-primary").click();
    expect(".modal").toHaveCount(2);
    expect(".o_dialog:not(.o_inactive_modal) .modal-body").toHaveText(
        "There are 3 records linked, upon confirming records will be deleted."
    );

    await contains(".o_dialog:not(.o_inactive_modal) .btn-primary").click();
});

test("add a selection field in non debug", async () => {
    expect.assertions(9);

    const arch = `<list><field name='display_name'/></list>`;
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].node.field_description.selection).toBe(
            '[["Value 1","Miramar"]]'
        );
        return editView(params, "list", arch);
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_selection").dragAndDrop(
        ".o_web_studio_hook"
    );
    await animationFrame();
    expect(".modal-content.o_web_studio_selection_editor").toHaveCount(1);
    expect(".modal .o_web_studio_selection_editor > li").toHaveCount(0);
    expect(".modal .btn-primary").toHaveClass("disabled");

    await contains(".modal .o_web_studio_add_selection input").edit("Value 1");

    expect(".modal .o_web_studio_selection_editor > li").toHaveCount(1);
    expect(".modal .o_web_studio_selection_editor > li span:contains(Value 1)").toHaveCount(1);

    await contains(".modal button.fa-pencil-square-o").click();
    expect(".modal .o_web_studio_selection_editor > li input").toHaveCount(1);
    expect(".modal .o_web_studio_selection_editor > li input:eq(0)").toHaveValue("Value 1");

    await contains(".modal .o_web_studio_selection_editor ul:first-child input").edit("Miramar", {
        confirm: false,
    });
    await contains(".modal .o_web_studio_selection_editor ul:first-child button.fa-check").click();
    expect(".modal .o_web_studio_selection_editor ul:first-child li").toHaveText("Miramar");

    await contains(".modal .btn-primary").click();
});

test("add a selection field in debug", async () => {
    expect.assertions(14);

    serverState.debug = "1";

    const arch = `<list><field name='display_name'/></list>`;
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].node.field_description.selection).toBe(
            '[["Value 2","Value 2"],["Value 1","My Value"],["Sulochan","Sulochan"]]'
        );
        return editView(params, "list", arch);
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_selection").dragAndDrop(
        ".o_web_studio_hook"
    );
    await animationFrame();
    expect(".modal-content.o_web_studio_selection_editor").toHaveCount(1);
    expect(".modal .o_web_studio_selection_editor > li").toHaveCount(0);
    expect(".modal .btn-primary").toHaveClass("disabled");

    await contains(".modal .o_web_studio_add_selection input").edit("Value 1");

    expect(".modal .o_web_studio_selection_editor > li").toHaveCount(1);
    expect(".modal .o_web_studio_selection_editor > li span:contains(Value 1)").toHaveCount(1);

    await contains(".modal #new .o-web-studio-interactive-list-item-input").edit("Value 2", {
        confirm: false,
    });
    await contains(".modal #new button.fa-check").click();
    expect(".modal .o_web_studio_selection_editor > li").toHaveCount(2);

    await contains(
        ".modal .o_web_studio_selection_editor ul:first-child .o-web-studio-interactive-list-edit-item"
    ).click();
    expect(".modal .o_web_studio_selection_full_edit").toHaveCount(1);
    expect(".o_web_studio_selection_full_edit label:nth-child(2) input").toHaveValue("Value 1");

    await contains(".o_web_studio_selection_full_edit label:nth-child(2) input").edit("My Value", {
        confirm: false,
    });
    await contains(".o_web_studio_selection_full_edit .fa-check").click();
    expect(".o_web_studio_selection_full_edit").toHaveCount(0);
    expect(
        ".modal .o_web_studio_selection_editor ul li:first-child .o-web-studio-interactive-list-item-label"
    ).toHaveText("My Value");

    await contains(".modal #new .o-web-studio-interactive-list-item-input").edit("Value 3", {
        confirm: false,
    });
    await contains(".modal #new button.fa-check").click();
    expect(".modal .o_web_studio_selection_editor > li").toHaveCount(3);

    await contains(".modal .o_web_studio_selection_editor > li:nth-child(3) .fa-trash-o").click();
    expect(".modal .o_web_studio_selection_editor > li").toHaveCount(2);

    await contains(
        ".modal .o_web_studio_selection_editor > li:nth-child(2) .o-draggable-handle"
    ).dragAndDrop(".modal .o_web_studio_selection_editor > li:first-child");
    expect(
        ".modal .o_web_studio_selection_editor ul li:first-child .o-web-studio-interactive-list-item-label"
    ).toHaveText("Value 2");

    await contains(".modal .o-web-studio-interactive-list-item-input").edit("Sulochan");
    await contains(".modal .btn-primary").click();
});

test("add a selection field with widget priority", async () => {
    expect.assertions(5);

    const arch = `<list><field name='display_name'/></list>`;
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].node.attrs.widget).toBe("priority");
        expect(params.operations[0].node.field_description.type).toBe("selection");
        expect(params.operations[0].node.field_description.selection).toEqual([
            ["0", "Normal"],
            ["1", "Low"],
            ["2", "High"],
            ["3", "Very High"],
        ]);
        return editView(params, "list", arch);
    });

    expect(".o_web_studio_list_view_editor table thead [data-studio-xpath]").toHaveCount(1);
    await contains(".o_web_studio_new_fields .o_web_studio_field_priority").dragAndDrop(
        ".o_web_studio_hook"
    );
    await advanceTime(4000);
    expect(".modal").toHaveCount(0);
});

test("invisible list editor", async () => {
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='display_name' column_invisible='1'/></list>`,
    });

    expect(".o_list_view [data-studio-xpath]").toHaveCount(0);
    expect("table thead th.o_web_studio_hook").toHaveCount(1);

    await contains(".o_web_studio_view").click();
    await contains(".o_web_studio_sidebar input#show_invisible").click();
    expect(".o_list_view [data-studio-xpath]").not.toHaveCount(0);
    expect("table thead th.o_web_studio_hook").toHaveCount(2);
});

test("list editor invisible element", async () => {
    Partner._records = [{ id: 1 }];
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `
            <list>
                <field name='display_name' class="my_super_name_class" />
                <field name='id' class="my_super_description_class" invisible="True"/>
            </list>`,
    });

    expect("td.my_super_name_class").toHaveCount(1);
    expect("td.my_super_name_class").toBeVisible();
    expect(".my_super_description_class").toHaveText("");

    await contains(".o_web_studio_view").click();
    await contains(".o_web_studio_sidebar input#show_invisible").click();

    expect("td.my_super_name_class").toBeVisible();
    expect(".my_super_description_class").toHaveText("1");
});

test("show invisible state is kept between sidebar panels", async () => {
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='display_name'/></list>`,
    });

    await contains(".o_web_studio_view").click();
    await animationFrame();
    expect("input#show_invisible").not.toBeChecked();

    await contains(".o_web_studio_sidebar input#show_invisible").click();
    expect("input#show_invisible").toBeChecked();

    await contains(".o_web_studio_new").click();
    await contains(".o_web_studio_view").click();
    expect("input#show_invisible").toBeChecked();
});

test("list editor with control node tag", async () => {
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><control><create string='Add a line'/></control></list>`,
    });

    expect(".o_list_view [data-studio-xpath]").toHaveCount(0);
    await contains(".o_web_studio_view").click();
    await contains(".o_web_studio_sidebar input#show_invisible").click();
    expect(".o_list_view [data-studio-xpath]").toHaveCount(0);
});

test("list editor invisible to visible on field", async () => {
    expect.assertions(6);
    serverState.userContext.lang = "fr_FR";
    const archReturn = `<list><field name='display_name'/><field name="id"/></list>`;

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list>
                <field name='display_name'/>
                <field name='id' column_invisible='1'/>
            </list>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.context.tz).toBe("taht");
        expect(params.context.lang).toBe(false);
        expect(params.operations[0].new_attrs.invisible).toBe("False");
        expect(params.operations[0].new_attrs.column_invisible).toBe("False");
        return editView(params, "list", archReturn);
    });

    await contains(".o_web_studio_view").click();
    await contains(".o_web_studio_sidebar input#show_invisible").click();
    await contains("thead th[data-studio-xpath='/list[1]/field[2]']").click();
    expect.verifySteps([]);
    await contains(".o_web_studio_sidebar input#invisible").click();
    expect.verifySteps(["edit_view"]);
});

test("list editor invisible to visible on field readonly", async () => {
    expect.assertions(5);

    const archReturn = `<list>
            <field name='display_name'/>
            <field name="id" column_invisible="True" readonly="True" />
        </list>`;

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list>
                <field name='display_name'/>
                <field name='id' readonly="True"/>
            </list>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.context.tz).toBe("taht");
        expect(params.operations[0].new_attrs.readonly).toBe(undefined);
        expect(params.operations[0].new_attrs.column_invisible).toBe("True");
        return editView(params, "list", archReturn);
    });

    await contains(".o_web_studio_view").click();
    await contains(".o_web_studio_sidebar input#show_invisible").click();
    await contains("thead th[data-studio-xpath='/list[1]/field[2]']").click();
    expect.verifySteps([]);
    await contains(".o_web_studio_sidebar input#invisible").click();
    expect.verifySteps(["edit_view"]);
});

test("list editor field", async () => {
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='display_name'/></list>`,
    });

    await contains(".o_web_studio_list_view_editor [data-studio-xpath]").click();
    expect(".o_web_studio_list_view_editor [data-studio-xpath]").toHaveClass(
        "o-web-studio-editor--element-clicked"
    );
    expect(".o_web_studio_properties").toHaveClass("active");
    expect(".o_web_studio_sidebar .o_web_studio_property_widget").toHaveCount(1);
    expect(".o_web_studio_sidebar input[name='string']").toHaveValue("Display name");
    expect(".o_web_studio_sidebar .o_web_studio_property_widget input").toHaveValue("Text (char)");
});

test("add group to field", async () => {
    expect.assertions(3);

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='display_name'/></list>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0]).toEqual({
            node: {
                attrs: { name: "display_name" },
                tag: "field",
            },
            new_attrs: { groups: [11] },
            position: "attributes",
            target: {
                attrs: { name: "display_name" },
                tag: "field",
                xpath_info: [
                    {
                        indice: 1,
                        tag: "list",
                    },
                    {
                        indice: 1,
                        tag: "field",
                    },
                ],
            },
            type: "attributes",
        });
        const arch = `<list>
                <field name='display_name' studio_groups='[{&quot;id&quot;:11, &quot;name&quot;: &quot;Unnamed&quot;}]'/>
            </list>`;
        return editView(params, "list", arch);
    });

    await contains(".o_web_studio_list_view_editor [data-studio-xpath]").click();
    await contains(".o_field_widget[name='group_ids'] input").click();
    await press("ArrowDown");
    await animationFrame();
    await contains(".dropdown-item").click();
    expect.verifySteps(["edit_view"]);
    expect(".o_limit_group_visibility .o_field_many2many_tags .badge.o_tag_color_0").toHaveCount(1);
});

test("sorting rows is disabled in Studio", async () => {
    Partner._records = [{ id: 1 }, { id: 2 }];

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list editable="1">
                <field name='id' widget='handle'/>
                <field name='display_name'/>
            </list>`,
    });

    expect(".ui-sortable-handle").toHaveCount(2);
    expect(queryAllTexts(".o_data_cell[name='display_name']")).toEqual(["partner,1", "partner,2"]);

    await contains("tbody tr:nth-child(2) .o_handle_cell").dragAndDrop("tbody tr:nth-child(1)");
    expect(queryAllTexts(".o_data_cell[name='display_name']")).toEqual(["partner,1", "partner,2"]);
});

test("List grouped should not be grouped", async () => {
    Partner._fields.priority = fields.Integer();
    Partner._fields.croissant = fields.Integer();
    Partner._records = [
        { priority: 1, croissant: 3 },
        { priority: 1, croissant: 5 },
    ];
    Partner._views = {
        list: `<list><field name='croissant' sum='Total Croissant'/></list>`,
        search: `<search><filter string="Priority" name="priority" domain="[]" context="{'group_by':'priority'}"/></search>`,
    };
    handleDefaultStudioRoutes();

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        name: "Partner",
        res_model: "partner",
        type: "ir.actions.act_window",
        view_mode: "list",
        context: { search_default_priority: "1" },
        views: [
            [false, "list"],
            [false, "search"],
        ],
    });

    expect(".o_list_view .o_list_table_grouped").toHaveCount(1);
    await contains(".o_web_studio_navbar_item").click();
    expect(".o_web_studio_list_view_editor .o_list_table_grouped").toHaveCount(0);
});

test("move a field in list", async () => {
    expect.assertions(4);

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list>
                <field name='id'/>
                <field name='display_name'/>
            </list>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0]).toEqual({
            node: {
                tag: "field",
                attrs: { name: "display_name" },
                xpath_info: [
                    {
                        indice: 1,
                        tag: "list",
                    },
                    {
                        indice: 2,
                        tag: "field",
                    },
                ],
            },
            position: "before",
            target: {
                tag: "field",
                attrs: { name: "id" },
                xpath_info: [
                    {
                        indice: 1,
                        tag: "list",
                    },
                    {
                        indice: 1,
                        tag: "field",
                    },
                ],
            },
            type: "move",
        });

        const arch = `<list>
            <field name='display_name'/>
            <field name='id'/>
        </list>`;
        return editView(params, "list", arch);
    });

    expect(queryAllTexts(".o_web_studio_list_view_editor th[data-name]")).toEqual([
        "Id",
        "Display name",
    ]);

    await contains(
        ".o_web_studio_list_view_editor th[data-studio-xpath='/list[1]/field[2]']"
    ).dragAndDrop("th.o_web_studio_hook");
    await animationFrame();
    expect.verifySteps(["edit_view"]);
    expect(queryAllTexts(".o_web_studio_list_view_editor th[data-name]")).toEqual([
        "Display name",
        "Id",
    ]);
});

test("list editor field with aggregate function", async () => {
    expect.assertions(13);

    Partner._fields.integer_field = fields.Integer();
    Partner._fields.float_field = fields.Float();
    Partner._fields.currency_id = fields.Many2one({ relation: "res.currency" });
    Partner._fields.money_field = fields.Monetary({ currency_field: "currency_id" });
    Partner._records = [
        {
            integer_field: 3,
            float_field: 3.14,
            money_field: 1.001,
        },
        {
            integer_field: 5,
            float_field: 6.66,
            money_field: 999.999,
        },
    ];

    let arch = `<list><field name="display_name"/><field name="float_field"/><field name="money_field"/><field name="integer_field"/></list>`;

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        const op = params.operations[params.operations.length - 1];
        if (op.new_attrs.sum !== "") {
            expect(op.new_attrs.sum).toBe("Sum of Integer field");
            arch = `<list><field name="display_name"/><field name="float_field"/><field name="money_field"/><field name="integer_field" sum="Sum of Integer field"/></list>`;
        } else if (op.new_attrs.avg !== "") {
            expect(op.new_attrs.avg).toBe("Average of Integer field");
            arch = `<list><field name="display_name"/><field name="float_field"/><field name="money_field"/><field name="integer_field" avg="Average of Integer field"/></list>`;
        } else if (op.new_attrs.sum === "" || op.new_attrs.avg == "") {
            arch = `<list><field name="display_name"/><field name="float_field"/><field name="money_field"/><field name="integer_field"/></list>`;
        }
        return editView(params, "list", arch);
    });

    await contains("thead th[data-studio-xpath]").click();
    expect(".o_web_studio_sidebar .o_web_studio_property_aggregate").toHaveCount(0);

    await contains("thead th[data-studio-xpath='/list[1]/field[2]']").click();
    expect(".o_web_studio_sidebar .o_web_studio_property_aggregate").toHaveCount(1);

    await contains("thead th[data-studio-xpath='/list[1]/field[3]']").click();
    expect(".o_web_studio_sidebar .o_web_studio_property_aggregate").toHaveCount(1);

    await contains("thead th[data-studio-xpath='/list[1]/field[4]']").click();
    expect(".o_web_studio_sidebar .o_web_studio_property_aggregate").toHaveCount(1);

    await contains(".o_web_studio_sidebar .o_web_studio_property_aggregate input").click();
    await contains(".o-dropdown-item:contains(Sum)").click();
    expect.verifySteps(["edit_view"]);
    expect("tfoot tr td.o_list_number:eq(0)").toHaveText("8");
    expect("tfoot tr td.o_list_number span:eq(0)").toHaveAttribute(
        "data-tooltip",
        "Sum of Integer field"
    );

    await contains(".o_web_studio_sidebar .o_web_studio_property_aggregate input").click();
    await contains(".o-dropdown-item:contains(Average)").click();
    expect.verifySteps(["edit_view"]);
    expect("tfoot tr td.o_list_number:eq(0)").toHaveText("4");
    expect("tfoot tr td.o_list_number span:eq(0)").toHaveAttribute(
        "data-tooltip",
        "Average of Integer field"
    );

    await contains(".o_web_studio_sidebar .o_web_studio_property_aggregate input").click();
    await contains(".o-dropdown-item:contains('No aggregation')").click();
    expect.verifySteps(["edit_view"]);
});

test("error during list rendering: undo", async () => {
    mockService("notification", {
        add: (message) => expect.step(`notification: ${message}`),
    });
    let triggerError;
    patchWithCleanup(ListRenderer.prototype, {
        setup() {
            super.setup();
            onWillRender(() => {
                if (triggerError) {
                    triggerError = false;
                    throw new Error("Error during rendering");
                }
            });
        },
    });

    const errorArch = "<list />";
    const arch = "<list><field name='id'/></list>";

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    onRpc("/web_studio/edit_view", (request) => {
        expect.step("edit_view");
        if (triggerError) {
            return editView(request, "list", errorArch);
        } else {
            return editView(request, "list", arch);
        }
    });

    await contains(".o_web_studio_list_view_editor [data-studio-xpath]").click();
    await contains(".o_web_studio_sidebar .o_web_studio_remove").click();
    triggerError = true;
    await contains(".modal .btn-primary").click();
    expect.verifySteps([
        "edit_view",
        "notification: The requested change caused an error in the view. It could be because a field was deleted, but still used somewhere else.",
        "edit_view",
    ]);

    expect(".o_web_studio_view_renderer").toHaveCount(1);
    expect(".o_web_studio_list_view_editor [data-studio-xpath]").toHaveCount(1);
    expect(".o_web_studio_sidebar .nav-link.active").toHaveText("View");
});

test("error in view edition: undo", async () => {
    expect.assertions(7);
    expect.errors(1);
    mockService("notification", {
        add: (message) => expect.step(`notification: ${message}`),
    });

    let triggerError = true;

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: "<list><field name='id'/></list>",
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        if (triggerError) {
            triggerError = false;
            return Promise.reject(new Error("Boom"));
        } else {
            expect(params.operations).toHaveLength(1);
        }
    });

    expect(".o_web_studio_list_view_editor [data-studio-xpath]").toHaveCount(1);

    await contains(".o_web_studio_list_view_editor [data-studio-xpath]").click();
    await contains(".o_web_studio_sidebar .o_web_studio_remove").click();
    await contains(".modal-dialog .btn-primary").click();

    expect.verifySteps([
        "edit_view",
        "notification: This operation caused an error, probably because a xpath was broken",
    ]);
    expect.verifyErrors(["Boom"]);

    expect(".o_web_studio_list_view_editor [data-studio-xpath]").toHaveCount(1);
    expect(".o_web_studio_sidebar .nav-link.active").toHaveText("View");

    await contains(".o_web_studio_list_view_editor [data-studio-xpath]").click();
    await contains(".o_web_studio_sidebar .o_web_studio_remove").click();
    await contains(".modal-dialog .btn-primary").click();

    expect.verifySteps(["edit_view"]);
});

test("Default group by field in sidebar", async () => {
    let editViewCount = 0;
    Partner._fields.display_name.store = true;

    const arch = `
        <list>
            <field name='id'/>
            <field name='display_name'/>
        </list>`;

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    onRpc("/web_studio/edit_view", (request) => {
        let newArch = arch;
        editViewCount++;
        if (editViewCount === 1) {
            newArch = `
                <list default_group_by='display_name'>
                    <field name='id'/>
                    <field name='display_name'/>
                </list>
            `;
        }
        return editView(request, "list", newArch);
    });

    await contains(".nav-tabs > li:nth-child(2) a").click();
    expect(".o_web_studio_property_default_group_by .o_select_menu").toHaveCount(1);

    await contains(".o_web_studio_property_default_group_by .o_select_menu input").click();
    expect(queryAllTexts(".o_select_menu_item")).toEqual([
        "Created on",
        "Display name",
        "Id",
        "Last Modified on",
    ]);

    await editSelectMenu(".o_web_studio_property_default_group_by .o_select_menu input", {
        index: 1,
    });
    expect(
        ".o_web_studio_property_default_group_by .o_select_menu .o_tag:contains(Display Name)"
    ).toHaveCount(1);
    expect(".o_web_studio_property_default_group_by + .alert").toHaveCount(1);

    await contains(".o_web_studio_property_default_group_by .o_tag .o_delete i").click();
    expect(".o_web_studio_property_default_group_by + .alert").toHaveCount(0);
});

test("click on a link doesn't do anything", async () => {
    expect.assertions(3);

    Partner._fields.m2o = fields.Many2one({ relation: "res.users" });
    Partner._records = [{ m2o: serverState.userId }];
    patchWithCleanup(ListEditorRenderer.prototype, {
        onTableClicked(ev) {
            expect.step("onTableClicked");
            expect(ev.defaultPrevented).toBe(false);
            super.onTableClicked(ev);
            expect(ev.defaultPrevented).toBe(true);
        },
    });

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name="display_name"/><field name="m2o" widget="many2one"/></list>`,
    });

    await contains("[name='m2o'] a").click();
    expect.verifySteps(["onTableClicked"]);
});

test("invisible relational are fetched", async () => {
    expect.assertions(4);

    Partner._fields.m2o = fields.Many2one({ relation: "res.users" });
    Partner._fields.o2m = fields.One2many({ relation: "res.users" });
    Partner._records = [
        {
            o2m: [serverState.userId],
            m2o: serverState.userId,
        },
    ];

    onRpc("partner", "web_search_read", (params) => {
        expect.step("web_search_read");
        expect(params.kwargs.specification).toEqual({
            m2o: { fields: { display_name: {} } },
            o2m: { fields: {} },
        });
    });

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name="o2m" invisible="True" /><field name="m2o" invisible="True"/></list>`,
    });

    expect(queryAllTexts("tbody .o_data_row")).toEqual([""]);
    await contains(".o_web_studio_view").click();
    await contains(".o_web_studio_sidebar #show_invisible").click();
    expect(queryAllTexts("tbody .o_data_row")).toEqual(["1 record Mitchell Admin"]);
    expect.verifySteps(["web_search_read"]);
});

test("List readonly attribute should not set force_save", async () => {
    expect.assertions(2);
    const arch = '<list><field name="display_name"/></list>';

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].new_attrs.readonly).toBe("True");
        expect(params.operations[0].new_attrs.force_save).toBe(undefined);
        return editView(params, "list", arch);
    });

    await contains(".o_web_studio_list_view_editor [data-name='display_name']").click();
    await contains(".o_web_studio_sidebar input#readonly").click();
});

test("change 'editable' and 'open_form_view' attribute", async () => {
    expect.assertions(8);
    Partner._records = [{ id: 1 }, { id: 2 }];
    let nbViewEdit = 0;

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field column_invisible="1" name="display_name"/></list>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        nbViewEdit++;
        if (nbViewEdit === 1) {
            expect(params.operations[0].new_attrs.editable).toBe("bottom");
            const newArch = `<list editable="bottom"><field column_invisible="1" name="display_name"/></list>`;
            return editView(params, "list", newArch);
        } else {
            expect(params.operations[1].new_attrs.open_form_view).toBe(true);
            const newArch = `<list editable="bottom" open_form_view="true"><field column_invisible="1" name="display_name"/></list>`;
            return editView(params, "list", newArch);
        }
    });

    await contains(".o_web_studio_view").click();
    expect(".o_web_studio_sidebar_checkbox").toHaveCount(6);

    await contains(".o_web_studio_sidebar .o_web_studio_property_editable input").click();
    await contains(".o-dropdown-item:contains('Add record at the bottom')").click();

    expect(".o_web_studio_sidebar_checkbox").toHaveCount(7);
    expect(".o_web_studio_sidebar_checkbox:eq(5)").toHaveText("Enable Mass Editing");
    expect(".o_web_studio_sidebar_checkbox:eq(6)").toHaveText("Show link to record");
    expect(".o_list_renderer .o_list_record_open_form_view").toHaveCount(0);

    await contains(".o_web_studio_sidebar_checkbox input:eq(6)").click();
    expect(".o_list_renderer .o_list_record_open_form_view").toHaveCount(2);
});

test("multi_edit is visible when can_edit is true", async () => {
    expect.assertions(4);

    const viewResults = [
        {
            new_attrs: { edit: true },
            result: `<list edit="true"><field name="display_name"/></list>`,
        },
        {
            new_attrs: { multi_edit: true },
            result: `<list multi_edit="true" edit="true"><field name="display_name"/></list>`,
        },
    ];

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list edit="false"><field name="display_name"/></list>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        const { new_attrs, result } = viewResults.shift();
        expect(params.operations.at(-1).new_attrs).toEqual(new_attrs);
        return editView(params, "list", result);
    });

    await contains(".o_web_studio_view").click();
    expect(".o_web_studio_sidebar_checkbox:contains('Enable Mass Editing')").toHaveCount(0);

    await contains("#edit").click();
    expect(".o_web_studio_sidebar_checkbox:contains('Enable Mass Editing')").toHaveCount(1);

    await contains("#multi_edit").click();
});

test("groupby fields should not be included", async () => {
    expect.assertions(2);
    Partner._fields.m2o = fields.Many2one({ relation: "res.users" });

    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `
            <list>
                <field name="display_name"/>
                <groupby name="m2o">
                    <field name="id" invisible="1"/>
                </groupby>
            </list>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].new_attrs).toEqual({
            column_invisible: "False",
            invisible: "False",
        });
    });

    await contains("th[data-name='display_name']").click();
    await contains(".o_web_studio_attrs").click();
    await contains(".modal .btn-primary").click();
    expect.verifySteps(["edit_view"]);
});

test("field column width in list editor", async () => {
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].new_attrs).toEqual({
            width: "100",
        });
    });
    await mountViewEditor({
        type: "list",
        resModel: "partner",
        arch: `<list><field name='display_name'/></list>`,
    });

    await contains(".o_web_studio_view_renderer [data-studio-xpath").click();
    expect(".o_web_studio_sidebar .o_web_studio_property_width").toHaveCount(1);
    await contains(".o_web_studio_sidebar .o_web_studio_property_width input").edit(100);
    expect.verifySteps(["edit_view"]);
});
