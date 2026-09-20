import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { edit, press, queryAllTexts } from "@odoo/hoot-dom";
import { animationFrame, Deferred } from "@odoo/hoot-mock";
import { onMounted } from "@odoo/owl";
import {
    contains,
    defineModels,
    fields,
    models,
    onRpc,
    patchWithCleanup,
    serverState,
} from "@web/../tests/web_test_helpers";
import { CodeEditor } from "@web/core/code_editor/code_editor";
import { PivotEditorSidebar } from "@web_studio/client_action/view_editor/editors/pivot/pivot_editor";
import { editView, mountViewEditor } from "../view_editor_tests_utils";

describe.current.tags("desktop");
class Partner extends models.Model {
    _name = "partner";
}

defineMailModels();
defineModels([Partner]);

test("show properties sidepanel on field selection", async () => {
    Partner._fields.display_name.help = "Display name";
    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form><group><field name='display_name'/></group></form>`,
    });

    expect(".o_web_studio_view_renderer .o-web-studio-editor--element-clickable").toHaveCount(2);
    expect(".o_web_studio_view_renderer .o_web_studio_hook").not.toHaveCount(0);
    await contains(
        ".o_web_studio_view_renderer .o-web-studio-editor--element-clickable .o_form_label"
    ).click();

    expect(".nav-link.active").toHaveText("Properties");
    expect(".o_web_studio_property").not.toHaveCount(0);
    expect(
        ".o_web_studio_view_renderer .o-web-studio-editor--element-clickable:has(> .o_form_label:contains('Display name'))"
    ).toHaveClass(["o-web-studio-editor--element-clicked"]);
    expect(".o_web_studio_sidebar .o_web_studio_property_widget input").toHaveValue("Text (char)");
    expect("#help").toHaveValue("Display name");
});

test("Sidebar should display all field's widgets", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form><group><field name='display_name'/></group></form>`,
    });
    await contains(".o_form_label").click();
    await contains(".o_select_menu_toggler").click();

    expect(queryAllTexts(".o_select_menu_item")).toEqual([
        "Badge (badge)",
        "Copy Text to Clipboard (CopyClipboardChar)",
        "Copy URL to Clipboard (CopyClipboardURL)",
        "Email (email)",
        "Image (image_url)",
        "Multiline Text (sms_widget)",
        "Multiline Text (text_emojis)",
        "Multiline Text (text)",
        "Phone (phone)",
        "Reference (reference)",
        "Stat Info (statinfo)",
        "Text (char_emojis)",
        "Text (char)",
        "URL (url)",
    ]);
});

test("Pivot sidebar should display display name measures", async () => {
    Partner._fields.age = fields.Integer();
    patchWithCleanup(PivotEditorSidebar.prototype, {
        get currentMeasureFields() {
            return [1234];
        },
    });

    onRpc("ir.model.fields", "web_search_read", () => ({
        records: [
            {
                id: 1234,
                display_name: "Age",
            },
        ],
    }));

    await mountViewEditor({
        type: "pivot",
        resModel: "partner",
        arch: `<pivot><field name="age" type="measure"/></pivot>`,
    });

    expect(".o_pivot_measures_fields .o_tag_badge_text").toHaveText("Age");
});

test("folds/unfolds the existing fields into sidebar", async () => {
    const arch = `
        <form>
            <group>
                <field name='display_name'/>
            </group>
        </form>`;
    onRpc("/web_studio/edit_view", (request) => editView(request, "form", arch));

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch,
    });

    expect(".o_web_studio_field_type_container").toHaveCount(2);
    expect(".o_web_studio_existing_fields_header i").toHaveClass(["fa-caret-right"]);
    expect(".o_web_studio_existing_fields_section").not.toHaveCount();

    await contains(".o_web_studio_existing_fields_header").click();

    expect(".o_web_studio_field_type_container").toHaveCount(3);
    expect(".o_web_studio_existing_fields_header i").toHaveClass(["fa-caret-down"]);
    expect(".o_web_studio_existing_fields_section").toBeVisible();

    await contains(`.o_web_studio_existing_fields .o_web_studio_field_integer`).dragAndDrop(
        ".o_inner_group .o_cell.o-draggable"
    );
    expect(".o_web_studio_existing_fields_section").toBeVisible();

    await contains(".o_web_studio_existing_fields_header").click();
    expect(".o_web_studio_field_type_container").toHaveCount(2);
    expect(".o_web_studio_existing_fields_header i").toHaveClass(["fa-caret-right"]);
    expect(".o_web_studio_existing_fields_section").not.toHaveCount();
});

test("change widget binary to image", async () => {
    Partner._fields.image = fields.Binary();
    const arch = `<form><field name='image'/></form>`;

    onRpc("/web_studio/edit_view", (request) => {
        expect.step("edit_view RPC has been called");
        return editView(request, "form", arch);
    });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch,
    });

    expect(".o_web_studio_form_view_editor .o-web-studio-editor--element-clickable").toHaveCount(1);
    await contains(
        ".o_web_studio_form_view_editor .o-web-studio-editor--element-clickable"
    ).click();
    expect(".o_web_studio_property_widget").toHaveCount(1);
    expect(".o_web_studio_form_view_editor .o-web-studio-editor--element-clickable").toHaveClass([
        "o-web-studio-editor--element-clicked",
    ]);

    await contains(".o_web_studio_property_widget .o_select_menu input").click();
    await contains(".o-dropdown-item:contains('Image (image)')").click();

    expect.verifySteps(["edit_view RPC has been called"]);
});

test("update sidebar after edition", async () => {
    expect.assertions(5);
    const arch = `
        <form>
            <group>
                <field name='display_name'/>
            </group>
        </form>`;

    onRpc("/web_studio/edit_view", (request) => {
        expect(".o_web_studio_sidebar input[name=string]").toHaveValue("test");
        expect.step("editView");
        return editView(request, "form", arch);
    });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch,
    });

    await contains("[data-field-name=display_name]").click();
    expect(".o-web-studio-editor--element-clicked[data-field-name=display_name]").toHaveCount(1);

    expect(".o_web_studio_sidebar input[name=string]").toHaveValue("Display name");
    await edit("test");
    await press("Tab");
    await animationFrame();

    expect(".o-web-studio-editor--element-clicked[data-field-name=display_name]").toHaveCount(1);
    expect.verifySteps(["editView"]);
});

test("default value in sidebar", async () => {
    Partner._fields.gender = fields.Selection({
        selection: [
            ["male", "Male"],
            ["female", "Female"],
        ],
    });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `
        <form>
            <group>
                <field name='display_name'/>
                <field name='gender' widget="radio"/>
            </group>
        </form>`,
    });

    onRpc("/web_studio/get_default_value", async (request) => {
        const { params } = await request.json();
        if (params.field_name === "display_name") {
            return { default_value: "yolo" };
        } else if (params.field_name === "gender") {
            return { default_value: "male" };
        }
    });

    await contains("[data-field-name=display_name]").click();
    expect(".o_web_studio_property input[name='default_value']").toHaveValue("yolo");

    expect(".o_field_widget[name='gender'] input[type='radio']").toHaveCount(2);
    await contains("[data-field-name='gender']").click();
    await contains(".o_web_studio_property_default_value .o_select_menu_toggler").click();
    expect(".o_web_studio_property_default_value .o_select_menu_toggler").toHaveValue("Male");
    expect(queryAllTexts(".o_select_menu_item")).toEqual(["Female", "Male"]);
});

test("default value for new field name", async () => {
    let editViewCount = 0;
    const arch = `<form><group><field name='display_name'/></group></form>`;

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        editViewCount++;
        const { params } = await request.json();
        if (editViewCount === 1) {
            expect(params.operations[0].node.field_description.name).toMatch(
                /^x_studio_char_field_.*$/
            );
        } else if (editViewCount === 2) {
            expect(params.operations[1].node.field_description.name).toMatch(
                /^x_studio_float_field_.*$/
            );
        }
        return editView(params, "form", arch);
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_char").dragAndDrop(
        ".o_inner_group .o_cell.o-draggable"
    );
    await contains(".o_web_studio_new_fields .o_web_studio_field_float").dragAndDrop(
        ".o_inner_group .o_cell.o-draggable"
    );
});

test("remove starting underscore from new field value", async () => {
    serverState.debug = "1";

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form><group><field name='display_name'/></group></form>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        const fieldName = params.operations[0].node.field_description.name;
        const arch = `<form><group><field name='${fieldName}'/><field name='display_name'/></group></form>`;
        Partner._fields[fieldName] = {
            type: "char",
            string: "Hello",
        };
        return editView(params, "form", arch);
    });

    onRpc("/web_studio/rename_field", () => true);

    await contains(".o_web_studio_new_fields .o_web_studio_field_char").dragAndDrop(
        ".o_inner_group .o_cell.o-draggable"
    );

    await contains(".o_web_studio_property input[name='technical_name']").click();
    await edit("__new");
    await press("Tab");
    await animationFrame();
    expect(".o_web_studio_property input[name='technical_name']").toHaveValue("new");
});

test("notebook and group not drag and drop in a group", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `
        <form>
            <group>
                <group>
                    <field name='display_name'/>
                </group>
                <group>
                </group>
            </group>
        </form>`,
    });

    onRpc("/web_studio/edit_view", () => expect.step("editView"));

    await contains(".o_web_studio_field_type_container .o_web_studio_field_tabs").dragAndDrop(
        ".o_group .o_cell.o-draggable"
    );
    expect.verifySteps([]);
    await contains(".o_web_studio_field_type_container .o_web_studio_field_columns").dragAndDrop(
        ".o_group .o_cell.o-draggable"
    );
    expect.verifySteps([]);
});

test("moving a field outside of a group doesn't have a highlight", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `
        <form>
            <sheet>
                <div class='notInAGroup' style='width:50px;height:50px'/>
                <group>
                    <div class='inAGroup' style='width:50px;height:50px'/>
                </group>
            </sheet>
        </form>`,
    });

    const drag1 = await contains(".o_web_studio_new_fields .o_web_studio_field_monetary").drag();
    await drag1.moveTo(".notInAGroup");
    expect(".o_web_studio_nearest_hook").toHaveCount(0);
    await drag1.cancel();

    const drag2 = await contains(".o_web_studio_new_fields .o_web_studio_field_monetary").drag();
    await drag2.moveTo(".inAGroup");
    expect(".o_web_studio_nearest_hook").toHaveCount(1);
    await drag2.cancel();
});

test("click on the 'More' Button", async () => {
    serverState.debug = "1";

    class View extends models.Model {
        _name = "ir.ui.view";
        _views = { form: `<form></form>` };
    }

    defineModels([View]);

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form></form>`,
    });

    await contains(".o_web_studio_editor .o_notebook_headers li:nth-child(2) a").click();
    expect(".o_web_studio_sidebar .o_web_studio_parameters").toHaveCount(1);
    await contains(".o_web_studio_sidebar .o_web_studio_parameters").click();
});

test("open xml editor of component view", async () => {
    serverState.debug = "1";

    // the XML editor lazy loads its libs and its templates so its start
    // method is monkey-patched to know when the widget has started
    const def = new Deferred();
    patchWithCleanup(CodeEditor.prototype, {
        setup() {
            super.setup();
            onMounted(() => def.resolve());
        },
    });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form/>`,
    });

    onRpc("/web_studio/get_xml_editor_resources", () => ({
        views: [
            {
                active: true,
                arch: "<form/>",
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

    await contains(".o_web_studio_sidebar .o_web_studio_view").click();
    await contains(".o_web_studio_open_xml_editor").click();
    await def;
    expect(".o_web_studio_code_editor.ace_editor").toHaveCount(1);
});

test("autofocus field label in the sidebar", async () => {
    Partner._fields.date = fields.Date();

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form><field name="display_name"/><field name="date"/></form>`,
    });

    onRpc("/web_studio/edit_view", (request) => {
        expect.step("edit_view");
        const newArch = `<form><field name="display_name" class="custom-class"/><field name="date"/></form>`;
        return editView(request, "form", newArch);
    });

    expect(".o_web_studio_sidebar .nav-link.o_web_studio_new").toBeFocused();
    await contains(".o_field_widget[name='display_name']").click();
    expect(".o_web_studio_sidebar input[name='string']").toBeFocused();
    await contains(".o_web_studio_sidebar input[name='class']").click();
    expect(".o_web_studio_sidebar input[name='class']").toBeFocused();
    await edit("custom-class");
    await press("Enter");
    await animationFrame();
    expect.verifySteps(["edit_view"]);
    expect(".o_web_studio_sidebar input[name='class']").toBeFocused();
    await contains(".o_field_widget[name='date']").click();
    expect(".o_web_studio_sidebar input[name='string']").toBeFocused();
});
