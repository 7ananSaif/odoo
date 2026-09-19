import { describe, expect, test } from "@odoo/hoot";
import {
    queryAll,
    queryAllAttributes,
    queryAllProperties,
    queryAllTexts,
    unload,
    queryFirst,
    waitForNone,
    waitFor,
} from "@odoo/hoot-dom";
import { animationFrame, runAllTimers } from "@odoo/hoot-mock";
import { Component, onMounted, xml } from "@odoo/owl";

import { mailModels, STORE_FETCH_ROUTES } from "@mail/../tests/mail_test_helpers";
import {
    followRelation,
    getTreeEditorContent,
    SELECTORS,
} from "@web/../tests/core/tree_editor/condition_tree_editor_test_helpers";
import {
    contains,
    defineActions,
    defineModels,
    editSelectMenu,
    fields,
    getService,
    makeMockServer,
    MockServer,
    models,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
    serverState,
} from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";
import { RelationalModel } from "@web/model/relational_model/relational_model";
import { charField } from "@web/views/fields/char/char_field";
import { ImageField } from "@web/views/fields/image/image_field";
import { WebClient } from "@web/webclient/webclient";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { COMPUTED_DISPLAY_OPTIONS } from "@web_studio/client_action/view_editor/interactive_editor/properties/type_widget_properties/type_specific_and_computed_properties";

import { RPCError } from "@web/core/network/rpc";
import { Setting } from "@web/views/form/setting/setting";
import {
    disableHookAnimation,
    editView,
    handleDefaultStudioRoutes,
    mountViewEditor,
    openStudio,
} from "@web_studio/../tests/view_editor_tests_utils";
import { formEditor } from "@web_studio/client_action/view_editor/editors/form/form_editor";

describe.current.tags("desktop");

const R_DATASET_ROUTE = /\/web\/dataset\/call_(button|kw)\/[\w.-]+\/(?<step>\w+)/;
const R_WEBCLIENT_ROUTE = /(?<step>\/web\/webclient\/\w+)/;

class Coucou extends models.Model {
    display_name = fields.Char();
    m2o = fields.Many2one({ string: "Product", relation: "product" });
    char_field = fields.Char();
    product_ids = fields.One2many({ string: "Products", relation: "product" });

    _records = [];
}

class Partner extends models.Model {
    display_name = fields.Char();
    image = fields.Binary();
    empty_image = fields.Binary();

    _records = [
        {
            id: 1,
            display_name: "jean",
        },
    ];
}

class Product extends models.Model {
    display_name = fields.Char();
    m2m_employees = fields.Many2many({ string: "Partners", relation: "partner" });
    m2o_partner = fields.Many2one({ string: "M2OPartner", relation: "partner" });
    coucou_id = fields.Many2one({ string: "Coucou", relation: "coucou" });
    partner_ids = fields.One2many({ string: "Partners", relation: "partner" });
    toughness = fields.Selection({
        string: "toughness",
        selection: [
            ["0", "Hard"],
            ["1", "Harder"],
        ],
    });

    _records = [{ id: 1, display_name: "A very good product" }];
}

defineModels({ ...mailModels, Coucou, Product, Partner });

test("Form editor should contains the view and the editor sidebar", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
            <sheet>
                <field name="display_name"/>
            </sheet>
        </form>
        `,
    });
    expect(".o_web_studio_editor_manager .o_web_studio_view_renderer").toHaveCount(1);
    expect(".o_web_studio_editor_manager .o_web_studio_sidebar").toHaveCount(1);
});

test("empty form editor", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form/>
        `,
    });
    expect(".o_web_studio_form_view_editor").toHaveCount(1);
    expect(".o_web_studio_form_view_editor .o-web-studio-editor--element-clickable").toHaveCount(0);
    expect(".o_web_studio_form_view_editor .o_web_studio_hook").toHaveCount(0);
});

test("Form editor view buttons can be set to invisible", async () => {
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].target.xpath_info).toEqual([
            {
                tag: "form",
                indice: 1,
            },
            {
                tag: "header",
                indice: 1,
            },
            {
                tag: "button",
                indice: 1,
            },
        ]);
        expect(params.operations[0].new_attrs).toEqual({ invisible: "True" });
        expect.step("edit_view");
    });
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
            <header>
                <button string="Test" type="object" class="oe_highlight"/>
            </header>
            <sheet>
                <field name="display_name"/>
            </sheet>
        </form>
        `,
    });
    expect(".o_web_studio_editor_manager .o_web_studio_view_renderer").toHaveCount(1);
    expect(".o_web_studio_editor_manager .o_web_studio_sidebar").toHaveCount(1);
    await contains(".o_form_renderer .o_statusbar_buttons > button").click();
    await contains(".o_notebook #invisible").click();
    expect.verifySteps(["edit_view"]);
});

test("Form editor view buttons label and class are editable from the sidebar", async () => {
    let count = 0;

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].target.xpath_info).toEqual([
            {
                tag: "form",
                indice: 1,
            },
            {
                tag: "header",
                indice: 1,
            },
            {
                tag: "button",
                indice: 1,
            },
        ]);
        if (count === 0) {
            expect(params.operations[0].new_attrs).toEqual({ string: "MyLabel" });
        } else {
            expect(params.operations[1].new_attrs).toEqual({ class: "btn-secondary" });
        }
        count++;
        expect.step("edit_view");
    });
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
            <header>
                <button string="Test" type="object" class="oe_highlight"/>
            </header>
            <sheet>
                <field name="display_name"/>
            </sheet>
        </form>
        `,
    });
    expect(".o_web_studio_editor_manager .o_web_studio_view_renderer").toHaveCount(1);
    expect(".o_web_studio_editor_manager .o_web_studio_sidebar").toHaveCount(1);
    await contains(".o_form_renderer .o_statusbar_buttons > button").click();
    expect("input[name=string]").toHaveValue("Test");
    await contains("input[name=string]").edit("MyLabel");
    expect.verifySteps(["edit_view"]);
    expect("input[name=class]").toHaveValue("oe_highlight");
    await contains("input[name=class]").edit("btn-secondary");
    expect.verifySteps(["edit_view"]);
});

test("optional field not in form editor", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
            <sheet>
                <field name="display_name"/>
            </sheet>
        </form>
        `,
    });
    await contains(".o_web_studio_view_renderer .o_field_char").click();
    expect(".o_web_studio_sidebar_optional_select").toHaveCount(0);
});

test("many2one field edition", async () => {
    onRpc("get_formview_action", () => {
        throw new Error("The many2one form view should not be opened");
    });
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
            <sheet>
                <field name="m2o"/>
            </sheet>
        </form>
        `,
    });
    expect(".o_web_studio_form_view_editor .o-web-studio-editor--element-clickable").toHaveCount(1);
    await contains(
        ".o_web_studio_form_view_editor .o-web-studio-editor--element-clickable"
    ).click();
    expect(queryAll(".o_web_studio_sidebar .o_web_studio_property").length > 0).toBe(true);
    expect(".o_web_studio_form_view_editor .o-web-studio-editor--element-clickable").toHaveClass(
        "o-web-studio-editor--element-clicked"
    );
});

test("image field is the placeholder when record is empty", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form>
            <sheet>
                <field name='empty_image' widget='image'/>
            </sheet>
        </form>
        `,
    });
    expect(".o_web_studio_form_view_editor .o_field_image").toHaveCount(1);
    expect(".o_web_studio_form_view_editor .o_field_image img").toHaveAttribute(
        "data-src",
        "/web/static/img/placeholder.png",
        {
            message: "default image in empty record should be the placeholder",
        }
    );
});

test("image field edition (change size)", async () => {
    onRpc("/web_studio/edit_view", (request) => {
        const newArch = `
                <form>
                    <sheet>
                        <field name='image' widget='image' options='{"size":[0, 270],"preview_image":"coucou"}'/>
                    </sheet>
                </form>
            `;
        return editView(request, "form", newArch);
    });

    patchWithCleanup(ImageField.prototype, {
        setup() {
            super.setup();
            onMounted(() => {
                expect.step(
                    `image, width: ${this.props.width}, height: ${this.props.height}, previewImage: ${this.props.previewImage}`
                );
            });
        },
    });
    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `
            <form>
                <sheet>
                    <field name='image' widget='image' options='{"size":[0, 90],"preview_image":"coucou"}'/>
                </sheet>
            </form>
        `,
    });
    expect(".o_web_studio_form_view_editor .o_field_image").toHaveCount(1);
    // the image should have been fetched
    expect.verifySteps(["image, width: undefined, height: 90, previewImage: coucou"]);
    await contains(".o_web_studio_form_view_editor .o_field_image").click();
    expect(".o_web_studio_property_size").toHaveCount(1);
    expect(".o_web_studio_property_size input").toHaveValue("Small");
    expect(".o_web_studio_form_view_editor .o_field_image").toHaveClass(
        "o-web-studio-editor--element-clicked"
    );
    await editSelectMenu(".o_web_studio_property_size input", { value: "Large" });
    // the image should have been fetched again
    expect.verifySteps(["image, width: undefined, height: 270, previewImage: coucou"]);
    expect(".o_web_studio_property_size input").toHaveValue("Large");
});

test("image size can be unset from the selection", async () => {
    let editViewCount = 0;

    onRpc("/web_studio/edit_view", (request) => {
        editViewCount++;
        let newArch;
        if (editViewCount === 1) {
            newArch = `<form>
                <sheet>
                    <field name='image' widget='image' class='oe_avatar' options='{"preview_image": "image"}'/>
                    <div class='oe_title'>
                        <field name='display_name'/>
                    </div>
                </sheet>
            </form>`;
        }
        return editView(request, "form", newArch);
    });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form>
            <sheet>
                <field name='image' widget='image' class='oe_avatar' options='{"preview_image": "image", "size": [0,90]}'/>
                <div class='oe_title'>
                    <field name='display_name'/>
                </div>
            </sheet>
        </form>`,
    });
    expect('.o_field_widget.oe_avatar[name="image"]').toHaveCount(1);
    await contains(".o_field_widget[name='image']").click();
    expect(".o_web_studio_property_size input").toHaveValue("Small");
    await contains(".o_web_studio_property_size input").click();
    await contains(".o_web_studio_property_size input").edit("");
});

test("signature field edition (change full_name)", async () => {
    let editViewCount = 0;
    let newFieldName;

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        editViewCount++;
        let newArch;
        if (editViewCount === 1) {
            expect(params.operations[0].node.attrs.widget).toBe("signature", {
                message: "'signature' widget should be there on field being dropped",
            });
            newFieldName = params.operations[0].node.field_description.name;
            newArch = `
                <form>
                    <group>
                        <field name='display_name'/>
                        <field name='m2o'/>
                        <field name='${newFieldName}' widget='signature'/>
                    </group>
                </form>
                `;
            Coucou._fields[newFieldName] = fields.Binary({
                string: "Signature",
            });
            return editView(params, "form", newArch);
        } else if (editViewCount === 2) {
            expect(params.operations[1].new_attrs.options).toBe('{"full_name":"display_name"}', {
                message: "correct options for 'signature' widget should be passed",
            });
            newArch = `
                <form>
                    <group>
                        <field name='display_name'/>
                        <field name='m2o'/>
                        <field name='${newFieldName}' widget='signature' options='{"full_name": "display_name"}'/>
                    </group>
                </form>
                `;
        } else if (editViewCount === 3) {
            expect(params.operations[2].new_attrs.options).toBe('{"full_name":"m2o"}', {
                message: "correct options for 'signature' widget should be passed",
            });
            newArch = `
                <form>
                    <group>
                        <field name='display_name'/>
                        <field name='m2o'/>
                        <field name='${newFieldName}' widget='signature' options='{"full_name": "m2o"}'/>
                    </group>
                </form>
                `;
        }
        return editView(params, "form", newArch);
    });
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `
            <form>
                <group>
                    <field name='display_name'/>
                    <field name='m2o'/>
                </group>
            </form>
        `,
    });
    await contains(".o_web_studio_new_fields .o_web_studio_field_signature").dragAndDrop(
        ".o_inner_group .o_web_studio_hook:first-child"
    );
    expect(".o_web_studio_form_view_editor .o_signature").toHaveCount(1);
    await contains(".o_web_studio_form_view_editor .o_signature").click();
    expect(".o_web_studio_property_full_name .o-dropdown").toHaveCount(1);
    expect(".o_web_studio_property_full_name input").toHaveValue("", {
        message: "the auto complete field should be empty by default",
    });
    await editSelectMenu(".o_web_studio_property_full_name input", { value: "Name" });
    expect(".o_web_studio_property_full_name input").toHaveValue("Display name");
    await editSelectMenu(".o_web_studio_property_full_name input", { value: "Product" });
    expect(".o_web_studio_property_full_name input").toHaveValue("Product");
});

test("integer field should come with 0 as default value", async () => {
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].node.field_description.type).toBe("integer");
        expect(params.operations[0].node.field_description.default_value).toBe("0");
    });

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `
            <form>
                <group>
                    <field name='display_name'/>
                </group>
            </form>`,
    });
    await contains(".o_web_studio_new_fields .o_web_studio_field_integer").dragAndDrop(
        ".o_web_studio_hook[data-position=before]"
    );
    expect.verifySteps(["edit_view"]);
});

test("supports multiple occurences of field", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form><group>
                <field name="display_name" widget="phone" options="{'enable_sms': false}" />
                <field name="display_name" invisible="1" />
            </group></form>`,
    });
    expect(
        ".o_web_studio_form_view_editor .o_inner_group .o-web-studio-editor--element-clickable"
    ).toHaveCount(1);
    await contains(".o_web_studio_sidebar .o_notebook_headers .nav-link:contains(View)").click();
    await contains(".o_web_studio_sidebar #show_invisible").click();
    expect(
        ".o_web_studio_form_view_editor .o_inner_group .o-web-studio-editor--element-clickable"
    ).toHaveCount(2);
    await contains(
        ".o_web_studio_form_view_editor .o_inner_group .o-web-studio-editor--element-clickable:eq(0)"
    ).click();
    // Would be true if not present in node's options
    expect(".o_web_studio_sidebar input[name='enable_sms']").not.toBeChecked();
    await contains(
        ".o_web_studio_form_view_editor .o_inner_group .o-web-studio-editor--element-clickable:eq(1)"
    ).click();
    expect(".o_web_studio_sidebar input[name='invisible']").toBeChecked();
});

test("options with computed display to have a dynamic sidebar list of options", async () => {
    let editCount = 0;
    // For this test, create fake options and make them tied to each other,
    // so the display and visibility is adapted in the editor sidebar
    patchWithCleanup(charField, {
        supportedOptions: [
            {
                label: "Fake super option",
                name: "fake_super_option",
                type: "boolean",
            },
            {
                label: "Suboption A",
                name: "suboption_a",
                type: "string",
            },
            {
                label: "Suboption B",
                name: "suboption_b",
                type: "boolean",
            },
            {
                label: "Suboption C",
                name: "suboption_c",
                type: "selection",
                choices: [
                    { label: "September 13", value: "sep_13" },
                    { label: "September 23", value: "sep_23" },
                ],
                default: "sep_23",
            },
            {
                label: "Suboption D",
                name: "suboption_d",
                type: "boolean",
            },
        ],
    });
    patchWithCleanup(COMPUTED_DISPLAY_OPTIONS, {
        suboption_a: {
            superOption: "fake_super_option",
            getInvisible: (value) => !value,
        },
        suboption_b: {
            superOption: "suboption_a",
            getReadonly: (value) => !value,
        },
        suboption_c: {
            superOption: "suboption_a",
            getInvisible: (value) => !value,
        },
        suboption_d: {
            superOption: "suboption_b",
            getValue: (value) => value,
            getReadonly: (value) => value,
        },
    });

    const arch = `<form><group>
        <field name="display_name"/>
    </group></form>`;
    onRpc("/web_studio/edit_view", (request) => {
        editCount++;
        if (editCount === 1) {
            const newArch =
                "<form><group><field name='display_name' options='{\"fake_super_option\":True}'/></group></form>";
            return editView(request, "form", newArch);
        }
        if (editCount === 2) {
            const newArch = `<form><group><field name='display_name' options="{'fake_super_option':True,'suboption_a':'Nice'}"/></group></form>`;
            return editView(request, "form", newArch);
        }
        if (editCount === 3) {
            const newArch = `<form><group><field name='display_name' options="{'fake_super_option':True,'suboption_a':'Nice','suboption_b':True}"/></group></form>`;
            return editView(request, "form", newArch);
        }
    });
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    await contains(".o_cell[data-field-name=display_name]").click();
    expect(".o_web_studio_property").toHaveCount(10);
    await contains("input[id=fake_super_option]").check();
    expect(".o_web_studio_property").toHaveCount(13);
    expect(".o_web_studio_property input[id='suboption_b']").not.toBeEnabled();
    expect(".o_web_studio_property input[id='suboption_d']").toBeEnabled();
    expect(".o_web_studio_property input[id='suboption_d']").not.toBeChecked();
    await contains("input[id=suboption_a]").edit("Nice");
    expect(".o_web_studio_property").toHaveCount(14);
    await contains("input[id=suboption_b]").check();
    expect(".o_web_studio_property").toHaveCount(14);
    expect(".o_web_studio_property input[id='suboption_d']").not.toBeEnabled();
    expect(".o_web_studio_property input[id='suboption_d']").toBeChecked();
    const computedOptions = queryAll(
        ".o_web_studio_property:nth-child(n+9):nth-last-child(n+5) label"
    );
    expect([...computedOptions].map((label) => label.textContent).join(", ")).toBe(
        "Suboption A, Suboption B, Suboption D, Suboption C",
        {
            message: "options are ordered and grouped with the corresponding super option",
        }
    );
});

test("field selection when editing a suboption", async () => {
    let editCount = 0;
    patchWithCleanup(charField, {
        supportedOptions: [
            {
                label: "Fake super option",
                name: "fake_super_option",
                type: "boolean",
            },
            {
                label: "Suboption",
                name: "suboption",
                type: "field",
            },
        ],
    });
    patchWithCleanup(COMPUTED_DISPLAY_OPTIONS, {
        suboption: {
            superOption: "fake_super_option",
            getInvisible: (value) => !value,
        },
    });

    const arch = `<form><group>
        <field name="display_name"/>
    </group></form>`;
    onRpc("/web_studio/edit_view", (request) => {
        editCount++;
        if (editCount === 1) {
            const newArch =
                "<form><group><field name='display_name' options='{\"fake_super_option\":True}'/></group></form>";
            return editView(request, "form", newArch);
        }
    });
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    await contains(".o_cell[data-field-name=display_name]").click();
    expect(".o_web_studio_property").toHaveCount(10);
    await contains("input[id=fake_super_option]").check();
    expect(".o_web_studio_property").toHaveCount(11);
    expect(".o_web_studio_property_suboption .o_select_menu").toHaveCount(1);
});

test("'class' attribute is editable in the sidebar with a tooltip", async () => {
    const arch = `<form>
        <header>
            <button string="Test" type="object" class="oe_highlight"/>
        </header>
        <sheet>
            <field name="display_name" class="studio"/>
        </sheet>
    </form>
    `;
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].new_attrs).toEqual({ class: "new_class" });
        return editView(params, "form", arch);
    });
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });
    await contains(".o_field_char").click();
    expect(".o_web_studio_property input[id=class]").toHaveCount(1);
    expect(".o_web_studio_property input[id=class]").toHaveValue("studio");
    const tooltip =
        "Use Bootstrap or any other custom classes to customize the style and the display of the element.";
    expect(".o_web_studio_property label:contains(Class) sup").toHaveAttribute(
        "data-tooltip",
        tooltip
    );
    await contains(".o_web_studio_property input[id=class]").edit("new_class");
    await contains(".o_statusbar_buttons button").click();
    expect(".o_web_studio_property input[id=class]").toHaveCount(1);
    expect(".o_web_studio_property input[id=class]").toHaveValue("oe_highlight");
    expect(".o_web_studio_property label:contains(Class) sup").toHaveAttribute(
        "data-tooltip",
        tooltip
    );
});

test("the name of the selected element is displayed in the sidebar", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
        <header>
            <button string="Test" type="object" class="oe_highlight"/>
        </header>
        <sheet>
            <group>
                <field name="display_name" class="studio"/>
                <field name="m2o"/>
            </group>
            <notebook>
                <page string="Notes"/>
            </notebook>
        </sheet>
    </form>
    `,
    });
    await contains(".o_inner_group").click();
    expect(".o_web_studio_sidebar h3").toHaveText("Column");
    await contains(".o_cell[data-field-name=display_name]").click();
    expect(".o_web_studio_sidebar h3").toHaveText("Field");
    expect(".o_web_studio_sidebar h3").toHaveClass("o_web_studio_field_char", {
        message: "type of the field is displayed with an icon",
    });
    await contains(".o_cell[data-field-name=m2o]").click();
    expect(".o_web_studio_sidebar h3").toHaveClass("o_web_studio_field_many2one");
    await contains(".o_statusbar_buttons button").click();
    expect(".o_web_studio_sidebar h3.o_web_studio_icon_container").toHaveText("Button");
    await contains(".nav-link:contains(Notes)").click();
    expect(".o_web_studio_sidebar h3.o_web_studio_icon_container").toHaveText("Page");
});

test("edit options and attributes on a widget node", async () => {
    let editCount = 0;

    class MyTestWidget extends Component {
        static template = xml`<div t-attf-class="bg-{{props.color}}" t-attf-style="width:{{props.width}}px;">Inspector widget</div>`;
        static props = ["*"];
    }
    registry.category("view_widgets").add("test_widget", {
        component: MyTestWidget,
        extractProps: ({ attrs, options }) => ({
            width: attrs.width,
            color: options.color,
        }),
        supportedAttributes: [
            {
                label: "Width",
                name: "width",
                type: "string",
            },
        ],
        supportedOptions: [
            {
                label: "Color option",
                name: "color",
                type: "string",
            },
        ],
    });

    const arch = `<form><group>
        <widget name="test_widget"/>
    </group></form>`;
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        editCount++;
        if (editCount === 1) {
            const newArch = `<form><group>
                <widget name="test_widget" width="30"/>
            </group></form>`;
            expect(params.operations[0].new_attrs).toEqual({ width: "30" });
            return editView(params, "form", newArch);
        }
        if (editCount === 2) {
            expect(params.operations[1].new_attrs).toEqual({ options: '{"color":"primary"}' });
            const newArch = `<form><group>
                <widget name="test_widget" width="30" options="{'color': 'primary'}"/>
            </group></form>`;
            return editView(params, "form", newArch);
        }
    });
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    await contains(".o_widget_test_widget").click();
    expect(".o_web_studio_property").toHaveCount(3);
    await contains("input[id=width]").edit("30");
    expect(".o_widget_test_widget div").toHaveStyle({ width: "30px" });
    await contains(".o_widget_test_widget").click();
    await contains("input[id=color]").edit("primary");
    expect(".o_widget_test_widget div").toHaveClass("bg-primary");
});

test("never save record -- hiding tab", async () => {
    const steps = [];
    onRpc("web_save", () => {
        steps.push("web_save");
    });
    patchWithCleanup(formEditor, {
        props() {
            const props = super.props(...arguments);
            class TestModel extends props.Model {}
            TestModel.Record = class extends TestModel.Record {
                _save() {
                    steps.push("_save");
                    return super._save(...arguments);
                }
            };
            props.Model = TestModel;
            return props;
        },
    });
    const arch = `<form><field name="display_name"/></form>`;
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    const visibilityStateProp = Object.getOwnPropertyDescriptor(
        Document.prototype,
        "visibilityState"
    );
    const prevVisibilitySate = document.visibilityState;
    Object.defineProperty(document, "visibilityState", {
        value: "hidden",
        configurable: true,
        writable: true,
    });

    document.dispatchEvent(new Event("visibilitychange"));
    await animationFrame();
    expect(steps).toEqual(["_save"]);
    Object.defineProperty(document, "visibilityState", visibilityStateProp);
    expect(document.visibilityState).toBe(prevVisibilitySate);
});

test("CharField can edit its placeholder_field option", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
        <header>
            <button string="Test" type="object" class="oe_highlight"/>
        </header>
        <sheet>
            <group>
                <field name="display_name" class="studio"/>
            </group>
        </sheet>
    </form>
    `,
    });
    await contains(".o_cell[data-field-name=display_name]").click();
    expect(".o_web_studio_property [name=placeholder_field]").toHaveCount(1);
    expect(".o_web_studio_property label[for=placeholder_field]").toHaveText(
        "Dynamic Placeholder?",
        {
            message: "the option is title Dynamic Placeholder and has a tooltip",
        }
    );
    expect(".o_web_studio_property [name=dynamic_placeholder]").toHaveCount(0, {
        message:
            "this options is not documented, because it does not make sense to edit this from studio",
    });
    expect(".o_web_studio_property [name=dynamic_placeholder_model_reference_field]").toHaveCount(
        0,
        {
            message:
                "this options is not documented, because it does not make sense to edit this from studio",
        }
    );
});

test("TextField can edit its placeholder", async () => {
    Coucou._fields.text = fields.Text();
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
        <sheet>
            <group>
                <field name="text" class="studio"/>
            </group>
        </sheet>
    </form>
    `,
    });
    await contains(".o_cell[data-field-name=text]").click();
    expect(".o_web_studio_property input[name=placeholder]").toHaveCount(1);
    expect(".o_web_studio_property [name=placeholder_field]").toHaveCount(1);
});

test("One2Many can edit its placeholder", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
        <sheet>
            <group>
                <field name="product_ids" class="studio"/>
            </group>
        </sheet>
    </form>
    `,
    });
    await contains(".o_cell[data-field-name=product_ids]").click();
    expect(".o_web_studio_property input[name=placeholder]").toHaveCount(1);
});

test("always invisible fields are flagged as not present in arch", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
            <field name="display_name" />
            <field name="m2o" invisible="True" />
            <field name="char_field" invisible="1" />
        </form>
    `,
    });

    expect(".o_web_studio_view_renderer .o_field_widget").toHaveCount(1);
    await contains(".o_web_studio_sidebar .o_web_studio_existing_fields_header").click();
    expect(".o_web_studio_sidebar .o_web_studio_existing_fields").toHaveText(
        "Char field\nCreated on\nId\nLast Modified on\nProduct\nProducts"
    );
});

test("disable creation(no_create options) in many2many_avatar_user and many2many_avatar_employee widget", async () => {
    onRpc("/web_studio/edit_view", async (request) => {
        const { params: args } = await request.json();
        expect.step("edit_view");
        expect(args.operations[0].new_attrs.options).toBe('{"no_create":true}');
    });
    await mountViewEditor({
        type: "form",
        resModel: "product",
        arch: /*xml*/ `
            <form>
                <sheet>
                    <group>
                        <field name="m2m_employees" widget="many2many_avatar_user"/>
                    </group>
                </sheet>
            </form>
        `,
    });
    await contains(".o_field_many2many_avatar_user[name='m2m_employees']").click();
    expect(".o_web_studio_sidebar #no_create").toHaveCount(1);
    expect(".o_web_studio_sidebar #no_create:checked").toHaveCount(0);

    await contains(".o_web_studio_sidebar #no_create").click();
    expect.verifySteps(["edit_view"]);
});

test("edit one2many form view (2 level) and check chatter allowed", async () => {
    Product._views = { "list,2": /*xml*/ `<list><field name='display_name'/></list>` };
    Partner._views = { list: /*xml*/ `<list><field name='display_name'/></list>` };
    Coucou._views = {
        "form,1": /*xml*/ `
            <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids'>
                        <form>
                            <sheet>
                                <group>
                                    <field name='partner_ids'>
                                        <form><sheet><group><field name='display_name'/></group></sheet></form>
                                    </field>
                                </group>
                            </sheet>
                        </form>
                    </field>
                </sheet>
            </form>
        `,
    };
    const { env: pyEnv } = await makeMockServer();
    const partnerId = pyEnv["partner"].create({ display_name: "jean" });
    const productId = pyEnv["product"].create({
        display_name: "xpad",
        partner_ids: [partnerId],
    });
    const coucouId1 = pyEnv["coucou"].create({
        display_name: "Coucou 11",
        product_ids: [productId],
    });
    defineActions([
        {
            xml_id: "studio.coucou_action",
            name: "coucouAction",
            res_model: "coucou",
            res_id: coucouId1,
            type: "ir.actions.act_window",
            views: [[false, "form"]],
        },
    ]);
    handleDefaultStudioRoutes();
    onRpc("ir.model", "studio_model_infos", () => ({
        is_mail_thread: true,
        record_ids: [],
    }));
    onRpc("name_search", ({ kwargs }) => {
        expect(kwargs.domain).toEqual(
            [
                ["relation", "=", "partner"],
                ["ttype", "in", ["many2one", "many2many"]],
                ["store", "=", true],
            ],
            {
                message:
                    "the domain should be correctly set when searching for a related field for new button",
            }
        );
        return [[1, "Partner"]];
    });
    onRpc("/*", (request) => {
        const route = new URL(request.url).pathname;
        const match = route.match(R_DATASET_ROUTE) || route.match(R_WEBCLIENT_ROUTE);
        const step = match?.groups?.step || route;
        if (
            ![
                ...STORE_FETCH_ROUTES,
                "/hr_attendance/attendance_user_data",
                "/web/bundle/web.assets_emoji",
            ].includes(step)
        ) {
            expect.step(step);
        }
    });

    await mountWithCleanup(WebClient);
    await animationFrame();
    expect.verifySteps(["/web/webclient/translations", "/web/webclient/load_menus"]);
    await getService("action").doAction("studio.coucou_action");
    expect.verifySteps(["/web/action/load", "get_views", "web_read"]);
    await openStudio();
    expect.verifySteps([
        "studio_model_infos",
        "get_views",
        "/web_studio/get_studio_view_arch",
        "web_read",
    ]);
    expect(".o_web_studio_add_chatter").toHaveCount(1);

    await contains(".o_field_one2many").click();

    await contains('.o_web_studio_editX2Many[data-type="form"]').click();
    await waitForNone(".o_web_studio_add_chatter");
    expect.verifySteps(["fields_get", "get_views", "web_read"]);

    await contains(".o_field_one2many").click();

    await contains('.o_web_studio_editX2Many[data-type="form"]').click();
    expect.verifySteps(["fields_get", "web_read"]);
    expect(".o_field_char").toHaveText("jean", {
        message: "the partner view form should be displayed.",
    });

    disableHookAnimation();
    await contains(".o_web_studio_field_char").dragAndDrop(".o_inner_group .o_web_studio_hook");
    expect.verifySteps(["/web_studio/edit_view"]);
});

test("edit one2many list view that uses parent key", async () => {
    Product._views = { "list,2": /*xml*/ `<list><field name='display_name'/></list>` };
    Coucou._views = {
        "form,1": /*xml*/ `
            <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids'>
                        <form>
                            <sheet>
                                <field name="m2o_partner"
                                    invisible="parent.display_name == 'coucou'"
                                    domain="[('display_name', '=', parent.display_name)]" />
                            </sheet>
                        </form>
                    </field>
                </sheet>
            </form>
        `,
    };
    const { env: pyEnv } = await makeMockServer();
    const partnerId = pyEnv["partner"].create({ display_name: "jacques" });
    const productId = pyEnv["product"].create({
        display_name: "xpad",
        m2o_partner: partnerId,
    });
    const coucouId1 = pyEnv["coucou"].create({
        display_name: "Coucou 11",
        product_ids: [productId],
    });
    defineActions([
        {
            xml_id: "studio.coucou_action",
            name: "coucouAction",
            res_model: "coucou",
            res_id: coucouId1,
            type: "ir.actions.act_window",
            views: [[false, "form"]],
        },
    ]);
    handleDefaultStudioRoutes();
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].new_attrs).toEqual({ invisible: "False" });
        expect.step("edit_view");
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();
    await getService("action").doAction("studio.coucou_action");
    await openStudio();
    // edit the x2m form view
    await contains(".o_field_one2many").click();
    await contains('.o_web_studio_editX2Many[data-type="form"]').click();
    expect(".o_field_widget[name='m2o_partner']").toHaveText("jacques", {
        message: "the x2m form view should be correctly rendered",
    });

    await contains('.o_field_widget[name="m2o_partner"]').click();
    // open the domain editor
    await waitForNone(".modal");
    expect(".o_web_studio_sidebar input#domain").toHaveValue(
        "[('display_name', '=', parent.display_name)]"
    );

    await contains(".o_web_studio_sidebar input#domain").click();
    expect(getTreeEditorContent()).toEqual([
        { level: 0, value: "all" },
        {
            level: 1,
            value: ["Display name", "is equal to", "parent.display_name"],
        },
    ]);
    expect(SELECTORS.addNewRule).toHaveCount(1);

    // Close the modal and remove the domain on invisible attr
    await contains(".btn-close").click();
    await contains("#invisible").click();
    expect.verifySteps(["edit_view"]);
});

test("move a field in one2many list", async () => {
    Coucou._views = {
        "form,1": /*xml*/ `
            <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids'>
                        <list>
                            <field name='m2o_partner'/>
                            <field name='coucou_id'/>
                        </list>
                    </field>
                </sheet>
            </form>
        `,
    };
    const { env: pyEnv } = await makeMockServer();
    const coucouId1 = pyEnv["coucou"].create({
        display_name: "Coucou 11",
        product_ids: pyEnv["product"].search([["display_name", "=", "xpad"]]),
    });
    defineActions([
        {
            xml_id: "studio.coucou_action",
            name: "coucouAction",
            res_model: "coucou",
            res_id: coucouId1,
            type: "ir.actions.act_window",
            views: [[1, "form"]],
        },
    ]);
    handleDefaultStudioRoutes();
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0]).toEqual({
            node: {
                tag: "field",
                attrs: { name: "coucou_id" },
                subview_xpath: "/form[1]/sheet[1]/field[2]/list[1]",
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
                attrs: { name: "m2o_partner" },
                subview_xpath: "/form[1]/sheet[1]/field[2]/list[1]",
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
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();
    await getService("action").doAction("studio.coucou_action");
    await openStudio();
    // edit the x2m form view
    await contains(".o_field_one2many").click();
    await contains('.o_web_studio_editX2Many[data-type="list"]').click();
    expect(queryAllTexts(".o_web_studio_list_view_editor th.o_column_sortable")).toEqual([
        "M2OPartner",
        "Coucou",
    ]);

    // move coucou at index 0
    await contains(".o_web_studio_list_view_editor th:contains('coucou')").dragAndDrop(
        "th.o_web_studio_hook"
    );
    expect.verifySteps(["edit_view"]);
});

test("One2Many list editor column_invisible in attrs ", async () => {
    Coucou._views = {
        "form,1": /*xml*/ `
            <form>
                <field name='product_ids'>
                    <list>
                        <field name="display_name" column_invisible="not parent.id" />
                    </list>
                </field>
            </form>
        `,
    };
    const { env: pyEnv } = await makeMockServer();
    pyEnv["coucou"].create({
        display_name: "Coucou 11",
        product_ids: pyEnv["product"].search([["display_name", "=", "xpad"]]),
    });
    defineActions([
        {
            xml_id: "studio.coucou_action",
            name: "coucouAction",
            res_model: "coucou",
            type: "ir.actions.act_window",
            views: [[1, "form"]],
        },
    ]);
    handleDefaultStudioRoutes();
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].new_attrs).toEqual({ readonly: "True" });
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();
    await getService("action").doAction("studio.coucou_action");
    await openStudio();
    // Enter edit mode of the O2M
    await contains(".o_field_one2many[name=product_ids]").click();
    await contains('.o_web_studio_editX2Many[data-type="list"]').click();
    await contains(".o_web_studio_sidebar .nav-link:contains('View')").click();
    await contains(".o_web_studio_sidebar input#show_invisible").click();
    // select the first column
    await contains("thead th[data-studio-xpath]").click();
    // enable readonly
    await contains(".o_web_studio_sidebar input#readonly").click();
    expect.verifySteps(["edit_view"]);
});

test("One2Many form datapoint doesn't contain the parent datapoint", async () => {
    /*
     * OPW-2125214
     * When editing a child o2m form with studio, the fields_get method tries to load
     * the parent fields too. This is not allowed anymore by the ORM.
     * It happened because, before, the child datapoint contained the parent datapoint's data
     */
    Coucou._views = {
        "form,1": /*xml*/ `
            <form>
                <field name='product_ids'>
                    <form>
                        <field name="display_name" />
                        <field name="toughness" />
                    </form>
                </field>
            </form>
        `,
    };
    Product._views = {
        "list,2": /*xml*/ `<list><field name="display_name" /></list>`,
    };
    const { env: pyEnv } = await makeMockServer();
    const coucouId1 = pyEnv["coucou"].create({ display_name: "Coucou 11" });
    defineActions([
        {
            xml_id: "studio.coucou_action",
            name: "coucouAction",
            res_model: "coucou",
            res_id: coucouId1,
            type: "ir.actions.act_window",
            views: [[1, "form"]],
        },
    ]);
    handleDefaultStudioRoutes();
    onRpc("product", "onchange", ({ args }) => {
        expect(Object.keys(args[3])).toEqual(["display_name", "toughness"]);
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();
    await getService("action").doAction("studio.coucou_action");
    await openStudio();
    await contains(".o_field_one2many").click();
    await contains('.o_web_studio_editX2Many[data-type="form"]').click();
});

test("'Add a button' is not shown when editing a list subview", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids'>
                        <list>
                            <field name='m2o_partner'/>
                            <field name='coucou_id'/>
                        </list>
                    </field>
                </sheet>
            </form>
        `,
    });
    expect(".o-web-studio-editor--add-button-action").toHaveCount(1);
    await contains(".o_form_view .o_list_view").click();
    await contains(".o_web_studio_editX2Many:contains(Edit List view)").click();
    expect(".o-web-studio-editor--add-button-action").toHaveCount(0);
});

test("invisible form editor", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `
            <form>
                <sheet>
                    <field name='display_name' invisible='1'/>
                    <group>
                        <field name='m2o' invisible="id != 42"/>
                    </group>
                </sheet>
            </form>`,
    });

    expect(".o_web_studio_form_view_editor .o_field_widget").toHaveCount(0);
    expect(".o_web_studio_form_view_editor .o-web-studio-editor--element-clickable").toHaveCount(1);
    expect(".o_web_studio_form_view_editor .o_web_studio_hook").toHaveCount(2);

    await contains(".o_web_studio_sidebar li:nth-child(2) a").click();
    await contains(".o_web_studio_sidebar input#show_invisible").click();

    expect(".o_web_studio_form_view_editor .o_web_studio_show_invisible").toHaveCount(2);
    expect(".o_web_studio_form_view_editor .o_invisible_modifier").toHaveCount(0);
    expect(".o_web_studio_form_view_editor .o_web_studio_hook").toHaveCount(3);
});

test("fields without value and label (outside of groups) are shown in form", async () => {
    Coucou._records = [
        {
            id: 1,
            display_name: "Kikou petite perruche",
        },
    ];

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        resId: 1,
        arch: `
            <form>
                <sheet>
                    <group>
                        <field name='id'/>
                        <field name='m2o'/>
                    </group>
                    <field name='display_name'/>
                    <field name='char_field'/>
                </sheet>
            </form>`,
    });

    expect(".o_web_studio_form_view_editor [name='id']").not.toHaveClass(
        "o_web_studio_widget_empty"
    );
    expect(".o_web_studio_form_view_editor [name='m2o']").not.toHaveClass(
        "o_web_studio_widget_empty"
    );
    expect(".o_web_studio_form_view_editor [name='m2o']").toHaveClass("o_field_empty");
    expect(".o_web_studio_form_view_editor [name='display_name']").not.toHaveClass(
        "o_web_studio_widget_empty"
    );
    expect(".o_web_studio_form_view_editor [name='char_field']").toHaveClass(
        "o_web_studio_widget_empty"
    );
    expect(".o_web_studio_form_view_editor [name='char_field']").toHaveText("Char field");
});

test("invisible group in form sheet", async () => {
    expect.assertions(8);

    const arch = `<form>
            <sheet>
                <group>
                    <group class="kikou" string="Kikou" invisible="True"/>
                    <group class="kikou2" string='Kikou2'/>
                </group>
            </sheet>
        </form>`;

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
                <sheet>
                    <group>
                        <group class="kikou" string='Kikou'/>
                        <group class="kikou2" string='Kikou2'/>
                    </group>
                </sheet>
            </form>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].new_attrs.invisible).toBe("True");
        return editView(params, "form", arch);
    });

    expect(".o_inner_group").toHaveCount(2);

    await contains(".o_inner_group:first-child").click();

    expect(".o_web_studio_property input#invisible").toHaveCount(1);
    expect(".o_web_studio_sidebar .o_web_studio_property input#invisible").not.toBeChecked();

    await contains(".o_web_studio_sidebar .o_web_studio_property input#invisible").click();
    await animationFrame();

    expect(".o_inner_group").toHaveCount(1);
    expect(".o-web-studio-editor--element-clicked").toHaveCount(0);
    expect(".o_web_studio_sidebar .o_web_studio_new").toHaveClass("active");

    await contains(".o_inner_group.kikou2").click();
    expect(".o_web_studio_sidebar .o_web_studio_sidebar_text input[name='string']").toHaveValue(
        "Kikou2"
    );
});

test("correctly display hook in form sheet", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `
            <form>
                <sheet>
                    <!-- hook here -->
                    <group>
                        <group/>
                        <group/>
                    </group>
                    <!-- hook here -->
                    <group>
                        <group/>
                        <group/>
                    </group>
                    <!-- hook here -->
                </sheet>
            </form>`,
    });

    expect(queryAllProperties(".o_form_sheet > div.o_web_studio_hook", "dataset")).toEqual([
        {
            xpath: "/form[1]/sheet[1]/*[1]",
            position: "before",
            type: "insideSheet",
        },
        {
            xpath: "/form[1]/sheet[1]/group[1]",
            position: "after",
            type: "afterGroup",
        },
        {
            xpath: "/form[1]/sheet[1]/group[2]",
            position: "after",
            type: "afterGroup",
        },
    ]);

    expect(".o_web_studio_form_view_editor .o_form_sheet > div.o_web_studio_hook").toHaveCount(3);

    expect(
        queryAllProperties(".o_form_sheet .o_inner_group > div.o_web_studio_hook", "dataset")
    ).toEqual([
        {
            xpath: "/form[1]/sheet[1]/group[1]/group[1]",
            position: "inside",
        },
        {
            xpath: "/form[1]/sheet[1]/group[1]/group[2]",
            position: "inside",
        },
        {
            xpath: "/form[1]/sheet[1]/group[2]/group[1]",
            position: "inside",
        },
        {
            xpath: "/form[1]/sheet[1]/group[2]/group[2]",
            position: "inside",
        },
    ]);

    expect(".o_web_studio_form_view_editor .o_form_sheet > div:nth-child(1)").toHaveClass(
        "o_web_studio_hook"
    );
    expect(".o_web_studio_form_view_editor .o_form_sheet > div:nth-child(3)").toHaveClass(
        "o_web_studio_hook"
    );
    expect(".o_web_studio_form_view_editor .o_form_sheet > div:nth-child(5)").toHaveClass(
        "o_web_studio_hook"
    );
});

test("correctly display hook in form with empty sheet", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `
            <form>
                <field name="display_name" invisible="1"/>
                <sheet/>
            </form>`,
    });

    expect(".o_form_sheet > div.o_web_studio_hook").toHaveCount(1);
    expect(".o_form_sheet > div.o_web_studio_hook").toHaveAttribute(
        "data-xpath",
        "/form[1]/sheet[1]"
    );
    expect(".o_form_sheet > div.o_web_studio_hook").toHaveAttribute("data-position", "inside");
    expect(".o_form_sheet > div.o_web_studio_hook").toHaveAttribute("data-type", "insideSheet");
});

test("correctly display hook below group title", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `
            <form>
                <sheet>
                    <group>
                        </group>
                        <group string='Kikou2'>
                        </group>
                    <group>
                        <field name='m2o'/>
                    </group>
                    <group string='Kikou'>
                        <field name='id'/>
                    </group>
                </sheet>
            </form>`,
    });

    // First group
    expect(
        ".o_web_studio_form_view_editor .o_inner_group:nth-child(2) .o_web_studio_hook"
    ).toHaveCount(1);

    expect(
        ".o_web_studio_form_view_editor .o_inner_group:nth-child(2) > div:nth-child(1)"
    ).toHaveClass("o_web_studio_hook");

    // Second group
    expect(
        ".o_web_studio_form_view_editor .o_inner_group:nth-child(3) .o_web_studio_hook"
    ).toHaveCount(1);

    expect(
        ".o_web_studio_form_view_editor .o_inner_group:nth-child(3) > div:nth-child(1)"
    ).toHaveText("KIKOU2");

    expect(
        ".o_web_studio_form_view_editor .o_inner_group:nth-child(3) > div:nth-child(2)"
    ).toHaveClass("o_web_studio_hook");

    // Third group
    expect(
        ".o_web_studio_form_view_editor .o_inner_group:nth-child(4) .o_web_studio_hook"
    ).toHaveCount(2);

    expect(
        ".o_web_studio_form_view_editor .o_inner_group:nth-child(4) > div:nth-child(1)"
    ).toHaveClass("o_web_studio_hook");

    expect(
        ".o_web_studio_form_view_editor .o_inner_group:nth-child(4) > div:nth-child(2)"
    ).toHaveText("Product");

    expect(
        ".o_web_studio_form_view_editor .o_inner_group:nth-child(4) [data-field-name='m2o'] + .o-web-studio-element-ghost + .o_web_studio_hook"
    ).toHaveCount(1);

    // Last group
    expect(
        ".o_web_studio_form_view_editor .o_inner_group:nth-child(5) .o_web_studio_hook"
    ).toHaveCount(2);

    expect(
        ".o_web_studio_form_view_editor .o_inner_group:nth-child(5) > div:nth-child(1)"
    ).toHaveText("KIKOU");

    expect(
        ".o_web_studio_form_view_editor .o_inner_group:nth-child(5) > div:nth-child(2)"
    ).toHaveClass("o_web_studio_hook");

    expect(
        ".o_web_studio_form_view_editor .o_inner_group:nth-child(5) > div:nth-child(3)"
    ).toHaveText("Id");

    expect(
        ".o_web_studio_form_view_editor .o_inner_group:nth-child(5) [data-field-name='id'] + .o-web-studio-element-ghost + .o_web_studio_hook"
    ).toHaveCount(1);
});

test("correctly display hook at the end of tabs -- empty group", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
                    <sheet>
                        <notebook>
                            <page string='foo'>
                            <group></group>
                            </page>
                        </notebook>
                    </sheet>
            </form>`,
    });

    expect(
        ".o_web_studio_form_view_editor .o_notebook .tab-pane.active > *:last-child"
    ).toHaveClass("o_web_studio_hook");
});

test("correctly display hook at the end of tabs -- multiple groups with content and an empty group", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
                <sheet>
                    <notebook>
                        <page string="foo">
                            <group>
                                <field name="m2o"/>
                            </group>
                            <group>
                                <field name="id"/>
                            </group>
                            <group></group>
                        </page>
                    </notebook>
                </sheet>
            </form>`,
    });

    expect(
        ".o_web_studio_form_view_editor .o_notebook .tab-pane.active > *:last-child"
    ).toHaveClass("o_web_studio_hook");
});

test("notebook page hooks", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `
            <form>
                <sheet>
                    <notebook>
                        <page string="field"><field name="display_name" /></page>
                        <page string="outer">
                            <group><group></group></group>
                        </page>
                        <page string='foo'>
                            <group>
                                <field name='m2o'/>
                            </group>
                            <group>
                                <field name='id'/>
                            </group>
                            <group></group>
                        </page>
                    </notebook>
                </sheet>
            </form>`,
    });

    expect(".o_notebook .tab-pane.active > .o_web_studio_hook").toHaveCount(1);
    expect(".o_notebook .tab-pane.active > .o_web_studio_hook").toHaveAttribute(
        "data-position",
        "inside"
    );
    expect(".o_notebook .tab-pane.active > .o_web_studio_hook").toHaveAttribute(
        "data-type",
        "page"
    );
    expect(".o_notebook .tab-pane.active > .o_web_studio_hook").toHaveAttribute(
        "data-xpath",
        "/form[1]/sheet[1]/notebook[1]/page[1]"
    );

    await contains(".o_notebook .nav-item a:eq(4)").click();
    expect(".o_notebook .tab-pane.active > .o_web_studio_hook").toHaveCount(1);
    expect(".o_notebook .tab-pane.active > .o_web_studio_hook").toHaveAttribute(
        "data-position",
        "after"
    );
    expect(".o_notebook .tab-pane.active > .o_web_studio_hook").toHaveAttribute(
        "data-type",
        "afterGroup"
    );
    expect(".o_notebook .tab-pane.active > .o_web_studio_hook").toHaveAttribute(
        "data-xpath",
        "/form[1]/sheet[1]/notebook[1]/page[2]/group[1]"
    );

    await contains(".o_notebook .nav-item a:eq(5)").click();
    expect(".o_notebook .tab-pane.active > .o_web_studio_hook").toHaveCount(1);
    expect(".o_notebook .tab-pane.active > .o_web_studio_hook").toHaveAttribute(
        "data-position",
        "inside"
    );
    expect(".o_notebook .tab-pane.active > .o_web_studio_hook").toHaveAttribute(
        "data-type",
        "page"
    );
    expect(".o_notebook .tab-pane.active > .o_web_studio_hook").toHaveAttribute(
        "data-xpath",
        "/form[1]/sheet[1]/notebook[1]/page[3]"
    );
});

test("notebook edition", async () => {
    expect.assertions(9);

    const arch = `
        <form>
            <sheet>
                <group>
                    <field name='display_name'/>
                </group>
                <notebook>
                    <page string='Kikou'>
                        <field name='id'/>
                    </page>
                </notebook>
            </sheet>
        </form>`;

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].node.tag).toBe("page");
        expect(params.operations[0].node.attrs.string).toBe("New Page");
        expect(params.operations[0].position).toBe("inside");
        expect(params.operations[0].target.tag).toBe("notebook");
        return editView(params, "form", arch);
    });

    expect(".o_content .o_notebook li").toHaveCount(2);

    await contains(".o_content .o_notebook li:first-child").click();

    expect(".o_content .o_notebook li:first-child").toHaveClass(
        "o-web-studio-editor--element-clicked"
    );

    expect(".o_web_studio_property").toHaveCount(2);
    expect(".o_web_studio_property .o_web_studio_sidebar_text input").toHaveValue("Kikou");
    expect(".o_limit_group_visibility").toHaveCount(1);

    await contains(".o_content .o_notebook li:last-child").click();
});

test("notebook with empty page", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
                <sheet>
                    <notebook>
                        <page string="field"></page>
                    </notebook>
                </sheet>
            </form>`,
    });

    await contains(".o_web_studio_view_renderer .o_notebook li").click();
    expect(".o_web_studio_properties").toHaveClass("active");

    expect(".o_web_studio_property").toHaveCount(2);
    expect(".o_web_studio_property input:eq(1)").toHaveValue("field");
});

test("notebook with empty page and fields inside the element", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
                <sheet>
                    <notebook>
                        <page string="Page"></page>
                        <field name='id' invisible='1'/>
                        <page string="Empty"></page>
                    </notebook>
                </sheet>
            </form>`,
    });

    await contains(".o_web_studio_view_renderer .o_notebook li").click();
    expect(".o_form_sheet .o_notebook_headers li:nth-child(2)").toHaveAttribute(
        "data-studio-xpath",
        "/form[1]/sheet[1]/notebook[1]/page[2]"
    );

    await contains(".o_form_sheet .o_notebook_headers li:nth-child(2) a").click();
    expect(".o_web_studio_property input:eq(1)").toHaveValue("Empty");
});

test("invisible notebook page in form", async () => {
    expect.assertions(9);
    const arch = `
        <form>
            <sheet>
                <notebook>
                    <page class="kikou" string='Kikou' invisible="True">
                        <field name='id'/>
                    </page>
                    <page class="kikou2" string='Kikou2'>
                        <field name='char_field'/>
                    </page>
                </notebook>
            </sheet>
        </form>`;

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
                <sheet>
                    <notebook>
                        <page class="kikou" string='Kikou'>
                            <field name='id'/>
                        </page>
                        <page class="kikou2" string='Kikou2'>
                            <field name='char_field'/>
                        </page>
                    </notebook>
                </sheet>
            </form>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].new_attrs.invisible).toBe("True");
        return editView(params, "form", arch);
    });

    expect(
        ".o_web_studio_view_renderer .o_notebook li.o-web-studio-editor--element-clickable"
    ).toHaveCount(2);

    await contains(".o_web_studio_view_renderer .o_notebook li").click();
    expect(".o_web_studio_sidebar input#invisible").toHaveCount(1);
    expect(".o_web_studio_sidebar input#invisible").not.toBeChecked();

    await contains(".o_web_studio_sidebar input#invisible").click();
    await animationFrame();
    expect(".o_web_studio_view_renderer .o_notebook li").toHaveCount(2);
    expect(".o_notebook li .kikou").not.toHaveCount();

    expect(".o-web-studio-editor--element-clicked").toHaveCount(0);
    expect(".o_web_studio_new").toHaveClass("active");

    await contains("li .kikou2").click();
    expect(".o_web_studio_property .o_web_studio_sidebar_text input").toHaveValue("Kikou2");
});

test("restore active notebook tab after adding/removing an element", async () => {
    const arch = `
        <form>
            <sheet>
                <notebook>
                    <page class="kikou" string='Kikou'>
                        <field name='id'/>
                    </page>
                    <page class="kikou2" string='Kikou2'>
                        <field name='char_field'/>
                    </page>
                </notebook>
            </sheet>
        </form>`;

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    onRpc("/web_studio/edit_view", (request) => {
        expect.step("edit_view");
        return editView(request, "form", arch);
    });

    await contains(".o_notebook .kikou2").click();
    await contains(".nav-link.o_web_studio_new").click();

    await contains(".o_web_studio_new_fields .o_web_studio_field_integer").dragAndDrop(
        ".o_notebook_content .o_web_studio_hook"
    );
    await animationFrame();
    await animationFrame();
    expect.verifySteps(["edit_view"]);
    expect(".kikou2").toHaveClass("active");
    expect(".o_web_studio_new").toHaveClass("active");

    await contains("div[name=char_field]").click();
    expect("div[name=char_field]").toHaveClass("o-web-studio-editor--element-clicked");

    await contains(".o_web_studio_remove").click();
    await contains(".modal .btn-primary").click();
    expect(".kikou2").toHaveClass("active");

    expect(".o_web_studio_new").toHaveClass("active");
    expect.verifySteps(["edit_view"]);
});

test("restore active notebook tab and element", async () => {
    const arch = `
        <form>
            <sheet>
                <notebook>
                    <page class="kikou" string='Kikou'>
                        <field name='id'/>
                    </page>
                    <page class="kikou2" string='Kikou2'>
                        <field name='char_field'/>
                    </page>
                </notebook>
            </sheet>
        </form>`;

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    onRpc("/web_studio/edit_view", (request) => {
        expect.step("edit_view");
        return editView(request, "form", arch);
    });

    // first, let's change the properties of a tab element
    await contains(".o_notebook .kikou2").click();
    await contains("input[name=string]").edit("Kikou deux");
    await animationFrame();
    await animationFrame();
    expect.verifySteps(["edit_view"]);
    expect(".o_form_sheet .nav-item:nth-child(2)").toHaveClass(
        "o-web-studio-editor--element-clicked"
    );

    // verify that the second tab does not keep the highlight when selecting another tab
    await contains(".o_notebook .kikou").click();
    await animationFrame();
    await animationFrame();
    expect(".o_form_sheet .nav-item:nth-child(1)").toHaveClass(
        "o-web-studio-editor--element-clicked"
    );

    // now let's change the properties of an inside element
    await contains(".o_notebook .kikou2").click();
    await contains("div[name=char_field]").click();
    expect("div[name=char_field]").toHaveClass("o-web-studio-editor--element-clicked");
    expect(".o_web_studio_properties").toHaveClass("active");

    await contains("input[name=placeholder]").edit("ae");
    await animationFrame();
    await animationFrame();
    expect("div[name=char_field]").toHaveClass("o-web-studio-editor--element-clicked");
    expect(".o_web_studio_properties").toHaveClass("active");
    expect.verifySteps(["edit_view"]);
});

test("restore active notebook tab after view property change", async () => {
    const arch = `
        <form>
            <sheet>
                <notebook>
                    <page class="kikou" string='Kikou'>
                        <field name='id'/>
                    </page>
                    <page class="kikou2" string='Kikou2'>
                        <field name='char_field'/>
                    </page>
                </notebook>
            </sheet>
        </form>`;

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    onRpc("/web_studio/edit_view", (request) => {
        expect.step("edit_view");
        return editView(request, "form", arch);
    });

    await contains(".o_notebook .kikou2").click();
    expect(".kikou2").toHaveClass("active");

    await contains(".nav-link.o_web_studio_view").click();
    expect(".o_web_studio_view").toHaveClass("active");

    await contains("input[name=edit]").click();
    await animationFrame();
    await animationFrame();
    expect.verifySteps(["edit_view"]);
    expect(".o_web_studio_view").toHaveClass("active");
    expect(".kikou2").toHaveClass("active");
});

test("label edition", async () => {
    expect.assertions(10);
    const arch = `
    <form>
        <sheet>
            <group>
                <label for='display_name' string='Kikou'/>
                <div><field name='display_name' nolabel='1'/></div>
                <field name="char_field"/>
            </group>
        </sheet>
    </form>`;

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].target).toEqual({
            tag: "label",
            attrs: {
                for: "display_name",
            },
            xpath_info: [
                {
                    indice: 1,
                    tag: "form",
                },
                {
                    indice: 1,
                    tag: "sheet",
                },
                {
                    indice: 1,
                    tag: "group",
                },
                {
                    indice: 1,
                    tag: "label",
                },
            ],
        });
        expect(params.operations[0].new_attrs).toEqual({ string: "Yeah" });
        return editView(params, "form", arch);
    });

    expect(".o_web_studio_form_view_editor label:eq(0)").toHaveText("Kikou");
    await contains(".o_web_studio_form_view_editor label:eq(0)").click();

    expect(".o_web_studio_form_view_editor label:eq(0)").toHaveClass(
        "o-web-studio-editor--element-clicked"
    );

    expect(".o_web_studio_property").toHaveCount(1);

    expect(".o_web_studio_sidebar_text input[id=string]").toHaveValue("Kikou");

    await contains(".o_web_studio_sidebar_text input[id=string]").edit("Yeah");

    expect("label.o_form_label:eq(1)").toHaveText("Char field");
    await contains("label.o_form_label:eq(1)").click();

    expect(".o_web_studio_form_view_editor label:first-child").not.toHaveClass(
        "o-web-studio-editor--element-clicked"
    );

    expect(".o_web_studio_property").toHaveCount(10);

    expect(".o_web_studio_sidebar_text input[id=string]").toHaveValue("Char field");
});

test("add a statusbar", async () => {
    expect.assertions(8);

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `
            <form>
                <sheet>
                    <group><field name='display_name'/></group>
                </sheet>
            </form>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations).toHaveLength(2);
        expect(params.operations[0]).toEqual({ type: "statusbar" });
        expect(params.operations[1].target).toEqual({ tag: "header" });
        expect(params.operations[1].position).toBe("inside");
        expect(params.operations[1].node.attrs).toEqual({
            widget: "statusbar",
            options: "{'clickable': '1'}",
        });
    });

    expect(".o_web_studio_form_view_editor .o_web_studio_statusbar_hook").toHaveCount(1);
    await contains(".o_web_studio_form_view_editor .o_web_studio_statusbar_hook").click();
    expect(".o_dialog .modal").toHaveCount(1);
    expect(
        ".o_dialog .o_web_studio_selection_editor li.o-draggable .o-web-studio-interactive-list-item-label"
    ).toHaveCount(3);
    await contains(".modal-footer .btn-primary").click();
});

test("move a field in form", async () => {
    expect.assertions(3);

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
                <sheet>
                    <group>
                        <field name='display_name'/>
                        <field name='char_field'/>
                        <field name='m2o'/>
                    </group>
                </sheet>
            </form>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0]).toEqual({
            node: {
                tag: "field",
                attrs: { name: "m2o" },
                xpath_info: [
                    {
                        indice: 1,
                        tag: "form",
                    },
                    {
                        indice: 1,
                        tag: "sheet",
                    },
                    {
                        indice: 1,
                        tag: "group",
                    },
                    {
                        indice: 3,
                        tag: "field",
                    },
                ],
            },
            position: "before",
            target: {
                tag: "field",
                xpath_info: [
                    {
                        indice: 1,
                        tag: "form",
                    },
                    {
                        indice: 1,
                        tag: "sheet",
                    },
                    {
                        indice: 1,
                        tag: "group",
                    },
                    {
                        indice: 1,
                        tag: "field",
                    },
                ],
                attrs: { name: "display_name" },
            },
            type: "move",
        });

        const arch = `<form>
                <sheet>
                    <group>
                        <field name='m2o'/>
                        <field name='display_name'/>
                        <field name='char_field'/>
                    </group>
                </sheet>
            </form>`;
        return editView(params, "form", arch);
    });

    expect(queryAllTexts(".o_web_studio_form_view_editor .o_form_sheet [data-field-name]")).toEqual(
        ["Display name", "Char field", "Product"]
    );

    await contains(".o-draggable[data-field-name='m2o']").dragAndDrop(
        ".o_inner_group .o_web_studio_hook"
    );
    await animationFrame();

    expect(queryAllTexts(".o_web_studio_form_view_editor .o_form_sheet [data-field-name]")).toEqual(
        ["Product", "Display name", "Char field"]
    );
});

test("form editor add avatar image", async () => {
    expect.assertions(15);

    const arch = `<form>
            <sheet>
                <div class='oe_title'>
                    <field name='display_name'/>
                </div>
            </sheet>
        </form>`;

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch,
    });

    let editViewCount = 0;
    onRpc("/web_studio/edit_view", async (request) => {
        editViewCount++;
        let newArch;
        const { params } = await request.json();

        if (editViewCount === 1) {
            expect(params.operations[0]).toEqual({
                field: "image",
                type: "avatar_image",
            });
            newArch = `<form>
                    <sheet>
                        <field name='image' widget='image' class='oe_avatar' options='{"preview_image": "image"}'/>
                        <div class='oe_title'>
                            <field name='display_name'/>
                        </div>
                    </sheet>
                </form>`;
        } else if (editViewCount === 2) {
            expect(params.operations[1]).toEqual({
                type: "remove",
                target: {
                    tag: "field",
                    attrs: {
                        name: "image",
                        class: "oe_avatar",
                    },
                    xpath_info: [
                        {
                            indice: 1,
                            tag: "form",
                        },
                        {
                            indice: 1,
                            tag: "sheet",
                        },
                        {
                            indice: 1,
                            tag: "field",
                        },
                    ],
                },
            });
            newArch = arch;
        } else if (editViewCount === 3) {
            expect(params.operations[2]).toEqual({
                field: "",
                type: "avatar_image",
            });
            Partner._fields.x_avatar_image = fields.Binary({ string: "Image" });
            newArch = `<form>
                    <sheet>
                        <field name='x_avatar_image' widget='image' class='oe_avatar' options='{"preview_image": "x_avatar_image"}'/>
                        <div class='oe_title'>
                            <field name='display_name'/>
                        </div>
                    </sheet>
                </form>`;
        }
        return editView(params, "form", newArch);
    });

    expect(".o_field_widget.oe_avatar").toHaveCount(0);
    expect(".oe_avatar.o_web_studio_avatar").toHaveCount(1);

    await contains(".oe_avatar.o_web_studio_avatar").click();

    expect(".modal .modal-body select > option").toHaveCount(3);
    expect(".modal .modal-body select > option[value='image']").toHaveCount(1);

    await contains("select[name='field']").select("image");
    await contains(".modal .modal-footer .btn-primary").click();

    expect(".o_field_widget.oe_avatar[name='image']").toHaveCount(1);
    expect(".oe_avatar.o_web_studio_avatar").toHaveCount(0);

    await contains(".oe_avatar").click();
    await contains(".o_web_studio_sidebar .o_web_studio_remove").click();

    expect(".modal-body").toHaveText("Are you sure you want to remove this field from the view?");

    await contains(".modal-footer .btn-primary").click();

    expect(".o_field_widget.oe_avatar").toHaveCount(0);
    expect(".oe_avatar.o_web_studio_avatar").toHaveCount(1);

    await contains(".oe_avatar.o_web_studio_avatar").click();

    expect(".modal .modal-body select > option.o_new").toHaveCount(1);

    await contains("select[name='field']").select("");
    await contains(".modal-footer .btn-primary").click();

    expect(".o_field_widget.oe_avatar[name='x_avatar_image']").toHaveCount(1);
    expect(".oe_avatar.o_web_studio_avatar").toHaveCount(0);
});

test("sidebar for a related field", async () => {
    Coucou._fields.related = fields.Char({ related: "m2o.display_name", string: "myRelatedField" });
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
                <sheet>
                    <div class='oe_title'>
                        <field name='related'/>
                    </div>
                </sheet>
            </form>`,
    });

    expect(".o_field_widget[name='related']").toHaveClass("o_web_studio_widget_empty");
    expect(".o_field_widget[name='related']").toHaveText("myRelatedField");
    await contains(".o_field_widget[name='related']").click();
    expect(".o_web_studio_properties").toHaveClass("active");
    expect("input[name='string']").toHaveValue("myRelatedField");
});

test("Phone field in form with SMS", async () => {
    expect.assertions(4);

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `
            <form><sheet>
                <group>
                    <field name='display_name' widget='phone' />
                </group>
            </sheet></form>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].node.attrs).toEqual({
            name: "display_name",
            widget: "phone",
        });
        expect(params.operations[0].new_attrs).toEqual({
            options: '{"enable_sms":false}',
        });
    });

    await contains(".o_form_label:contains('Display name')").click();
    expect(".o_web_studio_sidebar input[id='enable_sms']").toBeChecked();
    await contains(".o_web_studio_sidebar input[id='enable_sms']").click();
    expect.verifySteps(["edit_view"]);
});

test("modification of field appearing multiple times in view", async () => {
    expect.assertions(5);

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
                <group invisible="1">
                    <field name="display_name"/>
                </group>
                <group>
                    <field name="display_name"/>
                </group>
                <group>
                    <field name="char_field" />
                </group>
            </form>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].target.xpath_info).toEqual([
            {
                tag: "form",
                indice: 1,
            },
            {
                tag: "group",
                indice: 2,
            },
            {
                tag: "field",
                indice: 1,
            },
        ]);
        expect(params.operations[0].new_attrs).toEqual({ string: "Foo" });
    });

    expect(
        ".o_web_studio_form_view_editor .o_wrap_label.o-web-studio-editor--element-clickable:eq(0)"
    ).toHaveText("Display name");
    await contains(
        ".o_web_studio_form_view_editor .o_wrap_label.o-web-studio-editor--element-clickable"
    ).click();
    expect(".o_web_studio_property input[name='string']").toHaveValue("Display name");
    await contains(".o_web_studio_property input[name='string']").edit("Foo");
    expect.verifySteps(["edit_view"]);
});

test("Open form view with button_box in studio", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "partner",
        resId: 1,
        arch: `<form>
                <div name="button_box" class="oe_button_box" invisible="not display_name">
                    <button type="object" class="oe_stat_button" icon="fa-check-square">
                        <field name="display_name"/>
                    </button>
                </div>
            </form>`,
    });

    expect(".o-form-buttonbox button .o_field_widget span").toHaveText("jean");
});

test("new button in buttonbox", async () => {
    expect.assertions(6);

    const arch = `<form><sheet><field name='display_name'/></sheet></form>`;
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    onRpc("ir.model.fields", "web_name_search", () => [
        { id: 1, display_name: "Test Field (Test)" },
    ]);
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations).toEqual([
            { type: "buttonbox" },
            {
                type: "add",
                target: {
                    tag: "div",
                    attrs: {
                        class: "oe_button_box",
                    },
                },
                position: "inside",
                node: {
                    tag: "button",
                    field: 1,
                    string: "New button",
                    attrs: {
                        class: "oe_stat_button",
                        icon: "fa-diamond",
                    },
                },
            },
        ]);
        return editView(params, "form", arch);
    });

    await contains(".o_web_studio_button_hook").click();
    expect(".o_dialog .modal").toHaveCount(1);
    expect(".o_dialog .o_input_dropdown .o-autocomplete").toHaveCount(1);
    await contains(".modal-footer button:first-child").click();
    expect(".o_notification").toHaveCount(1);
    expect(".o_dialog .modal").toHaveCount(1);

    await contains(".o-autocomplete--input").click();
    await contains(".o-autocomplete .o-autocomplete--dropdown-item").click();
    await contains(".modal-footer button:first-child").click();
    expect(".o_dialog .modal").toHaveCount(0);
});

test("new button in buttonbox through 'Search more'", async () => {
    expect.assertions(7);

    const arch = `<form><sheet><field name='display_name'/></sheet></form>`;
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    MockServer.env["ir.model.fields"]._views = {
        list: `<list><field name="display_name"/></list>`,
    };

    onRpc("ir.model.fields", "web_name_search", () => [{ id: 1, display_name: "Select me" }]);

    onRpc("ir.model.fields", "web_search_read", () => ({
        records: [{ id: 1, display_name: "Select me" }],
    }));

    onRpc("ir.model.fields", "read", () => [{ id: 1, display_name: "Select me" }]);

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations).toEqual([
            { type: "buttonbox" },
            {
                type: "add",
                target: {
                    tag: "div",
                    attrs: {
                        class: "oe_button_box",
                    },
                },
                position: "inside",
                node: {
                    tag: "button",
                    field: 1,
                    string: "New button",
                    attrs: {
                        class: "oe_stat_button",
                        icon: "fa-diamond",
                    },
                },
            },
        ]);
        return editView(params, "form", arch);
    });

    await contains(".o_web_studio_button_hook").click();
    expect(".o_dialog .modal").toHaveCount(1);
    expect(".o_dialog .o_input_dropdown .o-autocomplete").toHaveCount(1);
    await contains(".modal-footer button:first-child").click();
    expect(".o_notification").toHaveCount(1);
    expect(".o_dialog .modal").toHaveCount(1);

    await contains(".o-autocomplete--input").click();
    await contains(".o_m2o_dropdown_option_search_more").click();
    await contains(".o_list_view .o_data_row .o_data_cell").click();
    expect(".o-autocomplete--input").toHaveValue("Select me");
    await contains(".modal-footer button:first-child").click();
    expect(".o_dialog .modal").toHaveCount(0);
});

test("buttonbox with invisible button, then show invisible", async () => {
    Coucou._records = [{ display_name: "someName", id: 99 }];

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        resId: 99,
        arch: `
            <form>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button name="someName" class="someClass" type="object"
                            invisible="display_name == &quot;someName&quot;" />
                    </div>
                    <field name='display_name'/>
                </sheet>
            </form>`,
    });

    expect(".o-form-buttonbox .o_web_studio_button_hook").toHaveCount(1);
    expect("button.someClass").toHaveCount(0);

    await contains(".o_web_studio_view").click();
    await contains(".o_web_studio_sidebar #show_invisible").click();

    expect("button.someClass").toHaveCount(1);
});

test("element removal", async () => {
    expect.assertions(10);

    const arch = `<form><sheet>
            <group>
                <field name='display_name'/>
                <field name='m2o'/>
            </group>
            <notebook><page name='page'><field name='id'/></page></notebook>
        </sheet></form>`;
    let editViewCount = 0;

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        editViewCount++;
        if (editViewCount === 1) {
            expect(params.operations[0].target).toInclude("xpath_info");
        } else if (editViewCount === 2) {
            expect(params.operations[1].target).toInclude("xpath_info");
        } else if (editViewCount === 3) {
            expect(params.operations[2].target.tag).toBe("group");
        } else if (editViewCount === 4) {
            expect(params.operations[3].target.tag).toBe("notebook");
            expect(params.operations[3].target.xpath_info.at(-1).tag).toBe("notebook");
        }

        return editView(params, "form", arch);
    });

    await contains("[data-field-name='display_name']").click();
    await contains(".o_web_studio_sidebar .o_web_studio_remove").click();
    expect(".modal-body").toHaveText("Are you sure you want to remove this field from the view?");
    await contains(".modal .btn-primary").click();

    await contains("[data-field-name='m2o']").click();
    await contains(".o_web_studio_sidebar .o_web_studio_remove").click();
    expect(".modal-body").toHaveText("Are you sure you want to remove this field from the view?");
    await contains(".modal .btn-primary").click();

    await contains(".o_inner_group.o-web-studio-editor--element-clickable").click();
    await contains(".o_web_studio_sidebar .o_web_studio_remove").click();
    expect(".modal-body").toHaveText("Are you sure you want to remove this column from the view?");
    await contains(".modal .btn-primary").click();

    await contains(".o_notebook li.o-web-studio-editor--element-clickable").click();
    await contains(".o_web_studio_sidebar .o_web_studio_remove").click();
    expect(".modal-body").toHaveText("Are you sure you want to remove this page from the view?");
    await contains(".modal .btn-primary").click();
    expect(editViewCount).toBe(4);
});

test("disable creation(no_create options) in many2many_tags widget", async () => {
    Product._fields.m2m = fields.Many2many({ relation: "product" });

    await mountViewEditor({
        type: "form",
        resModel: "product",
        arch: `
            <form>
                <sheet>
                    <group>
                        <field name='display_name'/>
                        <field name='m2m' widget='many2many_tags'/>
                    </group>
                </sheet>
            </form>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].new_attrs.options).toBe('{"no_create":true}');
    });

    await contains(".o_web_studio_view_renderer .o_field_many2many_tags").click();
    expect(".o_web_studio_sidebar #no_create").toHaveCount(1);
    expect(".o_web_studio_sidebar #no_create").not.toBeChecked();
    await contains(".o_web_studio_sidebar #no_create").click();
    expect.verifySteps(["edit_view"]);
});

test("disable creation(no_create options) in many2many_tags_avatar widget", async () => {
    Product._fields.m2m = fields.Many2many({ relation: "product" });

    await mountViewEditor({
        type: "form",
        resModel: "product",
        arch: `
            <form>
                <sheet>
                    <group>
                    <field name="m2m" widget="many2many_tags_avatar"/>
                    </group>
                </sheet>
            </form>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].new_attrs.options).toBe('{"no_create":true}');
    });

    await contains(".o_web_studio_view_renderer .o_field_many2many_tags_avatar").click();
    expect(".o_web_studio_sidebar #no_create").toHaveCount(1);
    expect(".o_web_studio_sidebar #no_create").not.toBeChecked();
    await contains(".o_web_studio_sidebar #no_create").click();
    expect.verifySteps(["edit_view"]);
});

test("notebook and group drag and drop after a group", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form><sheet>
                <group>
                <field name='display_name'/>
                </group>
            </sheet></form>`,
    });

    const drag1 = await contains(
        ".o_web_studio_field_type_container .o_web_studio_field_tabs"
    ).drag();
    await drag1.moveTo(".o_form_sheet > .o_web_studio_hook");

    expect(".o_web_studio_nearest_hook").toHaveCount(1);
    await drag1.cancel();

    const drag2 = await contains(
        ".o_web_studio_field_type_container .o_web_studio_field_columns"
    ).drag();
    await drag2.moveTo(".o_form_sheet > .o_web_studio_hook");

    expect(".o_web_studio_nearest_hook").toHaveCount(1);
    await drag2.cancel();
});

test("form: onchange is resilient to errors -- debug mode", async () => {
    serverState.debug = "1";
    patchWithCleanup(console, {
        warn: (msg) => expect.step(msg),
    });

    onRpc("onchange", () => {
        expect.step("onchange");
        const error = new RPCError();
        error.exceptionName = "odoo.exceptions.ValidationError";
        error.code = 0;
        error.message = "ValidationError";
        error.data = {
            name: "ValidationError",
        };
        return Promise.reject(error);
    });

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `
            <form>
                <div class="rendered">
                    <field name="display_name" />
                </div>
            </form>`,
    });

    expect.verifySteps([
        "onchange",
        "The onchange triggered an error. It may indicate either a faulty call to onchange, or a faulty model python side",
    ]);
    expect(".rendered").toHaveCount(1);
});

test("show an invisible x2many field", async () => {
    Partner._fields.o2m = fields.One2many({ relation: "product" });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form><group><field name='o2m' invisible="1" /></group></form>`,
    });

    expect("div[name='o2m']").toHaveCount(0);
    await contains(".o_web_studio_view").click();
    await contains(".o_web_studio_sidebar #show_invisible").click();
    expect("div[name='o2m']").toHaveCount(1);
});

test("supports displaying <setting> tag in innergroup", async () => {
    patchWithCleanup(Setting.prototype, {
        setup() {
            super.setup();
            expect.step(`setting instanciated. studioXpath: ${this.props.studioXpath}`);
        },
    });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `<form>
                <group>
                    <group class="o_settings_container">
                        <setting title="my setting">
                            <field name="display_name"/>
                        </setting>
                    </group>
                </group>
            </form>`,
    });

    expect(".o_setting_box .o_field_widget[name='display_name']").toHaveCount(1);
    expect.verifySteps([
        "setting instanciated. studioXpath: /form[1]/group[1]/group[1]/setting[1]",
    ]);
});

test("approval one rule by default", async () => {
    expect.assertions(8);

    let rules = [1];
    const arch = `<form>
            <header>
                <button name="0" string="Test" type="action" class="o_test_action_button"/>
            </header>
            <sheet>
                <field name="m2o"/>
            </sheet>
        </form>`;

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    onRpc("/web_studio/edit_view", (request) => editView(request, "form", arch));

    onRpc("studio.approval.rule", "create_rule", ({ args }) => {
        expect(args).toEqual(["coucou", null, "0", "2"]);
        return {};
    });

    onRpc("studio.approval.rule", "write", () => ({}));

    onRpc("studio.approval.rule", "get_approval_spec", () => {
        const allRules = Object.fromEntries(
            rules.map((id) => {
                const rule = {
                    action_id: "0",
                    approval_group_id: [1, "User types / Internal User"],
                    approver_ids: [],
                    can_validate: true,
                    domain: false,
                    exclusive_user: false,
                    id,
                    message: false,
                    method: false,
                    name: false,
                    notification_order: "1",
                    users_to_notify: [],
                };
                return [id, rule];
            })
        );
        return {
            all_rules: allRules,
            coucou: [[[false, false, "0"], { rules, entries: [] }]],
        };
    });

    expect(".o_form_statusbar button[name='0']").toHaveCount(1);
    await contains(".o_form_statusbar button[name='0']").click();
    expect(".o_web_studio_sidebar_approval > .o_studio_sidebar_approval_rule").toHaveCount(1);
    expect(".o_statusbar_buttons button img").toHaveCount(1);

    rules = [1, 2];
    await contains("a[name='create_approval_rule']").click();
    expect(".o_web_studio_sidebar_approval > .o_studio_sidebar_approval_rule").toHaveCount(2);
    expect(".o_statusbar_buttons button img").toHaveCount(2);

    rules = [1];
    await contains(".o_approval_archive:eq(0)").click();
    expect(".o_web_studio_sidebar_approval > .o_studio_sidebar_approval_rule").toHaveCount(1);
    expect(".o_statusbar_buttons button img").toHaveCount(1);
});

test("button rainbowman Truish value in sidebar", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `
            <form>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button name="action_confirm" type="object" effect="{}"/>
                    </div>
                </sheet>
            </form>`,
    });

    await contains("button.oe_stat_button[data-studio-xpath]").click();
    expect(".o_web_studio_sidebar [name='effect']").toBeChecked();
});

test("button rainbowman False value in sidebar", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `
            <form>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button name="action_confirm" type="object" effect="False"/>
                    </div>
                </sheet>
            </form>`,
    });

    await contains("button.oe_stat_button[data-studio-xpath]").click();
    expect(".o_web_studio_sidebar [name='effect']").not.toBeChecked();
});

test("edit the rainbowman effect from the sidebar", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `
            <form>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button name="action_confirm" type="object" effect="{'fadeout': 'medium'}"/>
                    </div>
                </sheet>
            </form>`,
    });

    let nbEdit = 0;
    onRpc("/web_studio/edit_view", async (request) => {
        expect.step("edit_view");
        const { params } = await request.json();
        nbEdit++;
        if (nbEdit === 1) {
            expect(params.operations[0].new_attrs).toEqual({
                effect: {
                    fadeout: "fast",
                },
            });
            const newArch = `
                <form>
                    <sheet>
                        <div class="oe_button_box" name="button_box">
                            <button name="action_confirm" type="object" effect="{'fadeout': 'fast'}"/>
                        </div>
                    </sheet>
                </form>`;
            return editView(params, "form", newArch);
        } else {
            expect(params.operations[1].new_attrs).toEqual({
                effect: {},
            });
        }
    });

    await contains("button.oe_stat_button[data-studio-xpath]").click();
    expect(".o_web_studio_sidebar [name='effect']").toBeChecked();
    expect(".o_web_studio_sidebar_select:eq(0) .o_select_menu .o_select_menu_toggler").toHaveValue(
        "Medium"
    );

    await contains(".o_web_studio_sidebar .o_select_menu input").click();
    await contains(".dropdown-item:contains('Fast')").click();
    expect.verifySteps(["edit_view"]);

    await contains(".o_web_studio_sidebar .o_select_menu input").click();
    await contains(".o_web_studio_sidebar .o_select_menu input").clear({ confirm: false });
    await runAllTimers();
    await queryFirst(".o_web_studio_sidebar .o_select_menu input").blur();
    expect.verifySteps(["edit_view"]);
});

test("Sets 'force_save' attribute when changing readonly attribute in form view", async () => {
    expect.assertions(4);
    const readonlyArch = `
        <form>
            <field name='display_name' readonly="True"/>
        </form>`;
    const arch = `
        <form>
            <field name='display_name'/>
        </form>`;
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    let nbEdit = 0;
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        const operation = params.operations[nbEdit];
        if (nbEdit === 0) {
            nbEdit++;
            expect(operation.new_attrs.readonly).toEqual("True");
            expect(operation.new_attrs.force_save).toEqual("1");
            return editView(params, "form", readonlyArch);
        } else {
            expect(operation.new_attrs.readonly).toEqual("False");
            expect(operation.new_attrs.force_save).toEqual("0");
            return editView(params, "form", arch);
        }
    });

    await contains(".o_web_studio_view_renderer .o_field_char").click();
    await contains(".o_web_studio_sidebar input[name='readonly']").check();
    await contains(".o_web_studio_sidebar input[name='readonly']").uncheck();
});

test("X2Many field widgets not using subviews", async () => {
    class NoSubView extends Component {
        static template = xml`<div>nosubview <t t-esc="this.props.record.fields[props.name].type"/></div>`;
        static props = ["*"];
    }
    registry.category("fields").add("nosubview", {
        component: NoSubView,
        supportedTypes: ["many2many", "one2many"],
    });

    Coucou._fields.product_ids = fields.One2many({ relation: "product" });

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form><field name="product_ids" widget="nosubview"/></form>`,
    });

    expect(".o_field_nosubview").toHaveText("nosubview one2many");
    expect(".o_field_nosubview").not.toHaveClass("o-web-studio-editor--element-clicked");

    await contains(".o_field_nosubview").click();

    expect(".o_field_nosubview").toHaveClass("o-web-studio-editor--element-clicked");
    expect(".o-web-studio-edit-x2manys-buttons").toHaveCount(0);
});

test("invisible relational are fetched", async () => {
    expect.assertions(4);

    Coucou._fields.product_ids = fields.One2many({ relation: "product" });
    Coucou._records = [{ product_ids: [1], m2o: 1 }];

    onRpc("coucou", "web_read", (params) => {
        expect.step("web_read");
        expect(params.kwargs.specification).toEqual({
            m2o: { fields: { display_name: {} } },
            product_ids: { fields: {} },
        });
    });

    await mountViewEditor({
        type: "form",
        resId: 1,
        resModel: "coucou",
        arch: `<form><field name="product_ids" invisible="True" /><field name="m2o" invisible="True" /></form>`,
    });

    expect(".o_field_widget").toHaveCount(0);
    await contains(".o_web_studio_view").click();
    await contains(".o_web_studio_sidebar #show_invisible").click();
    expect(".o_field_widget").toHaveCount(2);
    expect.verifySteps(["web_read"]);
});

test("Auto save: don't auto-save a form editor", async () => {
    onRpc("partner", "web_save", (params) => {
        expect.step("save");
    });

    patchWithCleanup(RelationalModel.prototype, {
        setup(...args) {
            super.setup(...args);
            this.bus.addEventListener("WILL_SAVE_URGENTLY", () =>
                expect.step("WILL_SAVE_URGENTLY")
            );
        },
    });

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `
            <form>
                <group>
                    <field name="display_name"/>
                </group>
            </form>`,
    });

    expect(".o_field_widget[name='display_name']").not.toHaveValue("test");

    const events = await unload();
    await animationFrame();
    expect(events.get("beforeunload")).not.toBeEmpty();
    expect.verifySteps([]);
});

test("fields in arch works correctly", async () => {
    Partner._fields.partner_ids = fields.One2many({ relation: "partner" });
    Partner._fields.some_field = fields.Char({ relation: "partner" });
    Partner._records = [];

    await mountViewEditor({
        type: "form",
        resModel: "partner",
        arch: `
            <form>
                <field name="display_name"/>
                <field name="partner_ids" >
                    <list>
                        <field name="some_field" />
                    </list>
                </field>
            </form>`,
    });

    await contains(".o_web_studio_existing_fields_header").click();
    expect(queryAllTexts(".o_web_studio_existing_fields .o_web_studio_component")).toEqual([
        "Created on",
        "Empty image",
        "Id",
        "Image",
        "Last Modified on",
        "Some field",
    ]);
});

test("Restrict drag and drop of notebook and group in a inner group", async () => {
    const arch = `<form>
            <sheet>
                <group>
                    <field name='display_name'/>
                </group>
            </sheet>
        </form>`;

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch,
    });

    let editViewCount = 0;
    onRpc("/web_studio/edit_view", (request) => {
        editViewCount++;
        return editView(request, "form", arch);
    });

    expect(".o_inner_group").toHaveCount(1);
    await contains(".o_web_studio_field_type_container .o_web_studio_field_tabs").dragAndDrop(
        ".o_inner_group"
    );
    await animationFrame();
    expect(editViewCount).toBe(0);
    await contains(".o_web_studio_field_type_container .o_web_studio_field_columns").dragAndDrop(
        ".o_inner_group"
    );
    expect(editViewCount).toBe(0);
});

test("edit_view route includes the context of the action", async () => {
    Coucou._records = [{ id: 1 }];
    Coucou._views = {
        form: /*xml */ `
           <form>
               <field name="display_name" />
           </form>`,
    };

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.context.action_key).toBe("some_context_value");
    });

    handleDefaultStudioRoutes();
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        type: "ir.actions.act_window",
        res_model: "coucou",
        res_id: 1,
        views: [[false, "form"]],
        context: { action_key: "some_context_value" },
    });

    await contains(".o_web_studio_navbar_item button").click();
    await contains(".o_web_studio_form_view_editor div[name='display_name']").click();
    await contains(".o_web_studio_sidebar input[name='string']").edit("new Label");
    expect.verifySteps(["edit_view"]);
});

test("subview's buttonbox form doesn't pollute main one", async () => {
    Coucou._fields.product_ids = fields.One2many({ relation: "product" });
    Coucou._records = [{ product_ids: [1] }];

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        resId: 1,
        arch: `<form>
                <field name="product_ids">
                    <form>
                        <div name="button_box">
                            <button name="some_action" type="object" string="my_action"/>
                        </div>
                        <field name="display_name" />
                    </form>
                    <list><field name="display_name" /></list>
                </field>
            </form>`,
    });

    expect(".o-form-buttonbox button").toHaveCount(1);
    expect(".o-form-buttonbox button").toHaveClass("o_web_studio_button_hook");
    expect("button[name='some_action']").toHaveCount(0);

    await contains(".o_field_x2many").click();
    await contains(".o_web_studio_editX2Many[data-type='form']").click();

    expect(".o-form-buttonbox").toHaveCount(1);
    expect(".o-form-buttonbox .o_web_studio_button_hook").toHaveCount(0);
    expect(".o-form-buttonbox button[name='some_action']").toHaveCount(0);
});

test("cannot add a related properties field", async () => {
    Product._fields.properties = fields.Properties({
        definition_record: "coucou",
        definition_record_field: "definition",
    });

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form><group><field name="display_name"/></group></form>`,
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_related").dragAndDrop(
        ".o_web_studio_form_view_editor .o_web_studio_hook"
    );
    await animationFrame();
    expect(".modal .o_model_field_selector").toHaveCount(1);

    await contains(".modal .o_model_field_selector").click();
    await followRelation(); // Product

    expect(
        queryAllTexts(
            ".o_popover .o_model_field_selector_popover_page .o_model_field_selector_popover_item"
        )
    ).toEqual([
        "Coucou",
        "Created on",
        "Display name",
        "Id",
        "Last Modified on",
        "M2OPartner",
        "Partners",
        "Partners",
        "toughness",
    ]);
});

test("InnerGroup without OuterGroup", async () => {
    expect.assertions(4);

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
                <group>
                    <div>
                        <field name="display_name"/>
                    </div>
                    <field name="char_field"/>
                </group>
            </form>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        expect.step("edit_view");
        const { params } = await request.json();
        const { target, position, type } = params.operations[0];
        expect(target).toEqual({
            tag: "div",
            attrs: {},
            xpath_info: [
                { tag: "form", indice: 1 },
                { tag: "group", indice: 1 },
                { tag: "div", indice: 1 },
            ],
        });
        expect(position).toBe("after");
        expect(type).toBe("add");
    });

    await contains(".o_web_studio_new_fields .o_web_studio_field_integer").dragAndDrop(
        ".o_web_studio_hook:eq(1)"
    );
    await animationFrame();
    expect.verifySteps(["edit_view"]);
});

test("remove empty o_td_label", async () => {
    expect.assertions(3);

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form><sheet><group><group><div class="o_td_label"/></group></group></sheet></form>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        expect.step("edit_view");
        const { params } = await request.json();
        const { target, type } = params.operations[0];
        expect(target).toEqual({
            tag: "div",
            attrs: { class: "o_td_label" },
            xpath_info: [
                { tag: "form", indice: 1 },
                { tag: "sheet", indice: 1 },
                { tag: "group", indice: 1 },
                { tag: "group", indice: 1 },
                { tag: "div", indice: 1 },
            ],
        });
        expect(type).toBe("remove");
    });

    await contains(".o-web-studio-editor--element-clickable .o_td_label").click();
    await contains(".o_web_studio_sidebar .o_web_studio_remove").click();
    await contains(".o_dialog .btn-primary").click();
    expect.verifySteps(["edit_view"]);
});

test("don't show span, fields in button box", async () => {
    Coucou._records = [{ id: 1 }];

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        resId: 1,
        arch: `<form><sheet><div class="oe_button_box" name="button_box">
                <span id="button_worksheet" invisible="1"/>
                <field name="char_field" invisible="1"/>
                <button name="action_visible" type="object" invisible="id != 1" class="oe_stat_button" icon="fa-star">
                    <field name="id" widget="statinfo"/>
                </button>
                <button name="action_invisible" type="object" invisible="id == 1" class="oe_stat_button" icon="fa-gear">
                    <field name="id" widget="statinfo"/>
                </button>
            </div></sheet></form>`,
    });
    expect(".o-form-buttonbox button[name=action_visible]").toHaveCount(1);
    expect(".o-form-buttonbox button[name=action_invisible]").toHaveCount(0);
    await contains(".o_web_studio_view").click();
    await contains(".o_web_studio_sidebar input#show_invisible").click();
    expect(".o-form-buttonbox button[name=action_visible]").toHaveCount(1);
    expect(".o-form-buttonbox button[name=action_invisible]").toHaveCount(1);
    expect(".o-form-buttonbox span#button_worksheet").toHaveCount(0);
    expect(".o-form-buttonbox .o_field_widget[name=char_field]").toHaveCount(0);
});

test("button_box: few visible buttons and no invisible buttons", async () => {
    Coucou._records = [{ id: 1 }];

    const editor = await mountViewEditor({
        type: "form",
        resModel: "coucou",
        resId: 1,
        arch: `<form>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button name="one" type="object" className="oe_stat_button" icon="fa-star">
                            <field name="id" widget="statinfo"/>
                        </button>
                        <button name="two" type="object" className="oe_stat_button" icon="fa-star">
                            <field name="id" widget="statinfo"/>
                        </button>
                    </div>
                    <group><group><field name="id"/></group></group>
                </sheet>
            </form>`,
    });
    expect(editor.env.services.ui.size).toBe(4);

    expect(".o_form_sheet_bg > div > .o-form-buttonbox button:first-child").toHaveClass(
        "o_web_studio_add_element"
    );
    expect(queryAllAttributes(".o_form_sheet_bg > div > .o-form-buttonbox button", "name")).toEqual(
        [null, "one", "two"]
    );
    expect(queryAllAttributes(".o_form_sheet_bg > .o-form-buttonbox button", "name")).toEqual([]);

    await contains(".o_web_studio_view").click();
    await contains(".o_web_studio_sidebar input#show_invisible").click();

    expect(".o_form_sheet_bg > div > .o-form-buttonbox button:first-child").toHaveClass(
        "o_web_studio_add_element"
    );
    expect(queryAllAttributes(".o_form_sheet_bg > div > .o-form-buttonbox button", "name")).toEqual(
        [null, "one", "two"]
    );
    expect(queryAllAttributes(".o_form_sheet_bg > .o-form-buttonbox button", "name")).toEqual([]);
});

test("button_box: few mixed buttons", async () => {
    Coucou._records = [{ id: 1 }];

    const editor = await mountViewEditor({
        type: "form",
        resModel: "coucou",
        resId: 1,
        arch: `<form>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button name="one" type="object" className="oe_stat_button" icon="fa-star">
                            <field name="id" widget="statinfo"/>
                        </button>
                        <button name="two" type="object" className="oe_stat_button" icon="fa-star" invisible="id != 5">
                            <field name="id" widget="statinfo"/>
                        </button>
                    </div>
                    <group><group><field name="id"/></group></group>
                </sheet>
            </form>`,
    });
    expect(editor.env.services.ui.size).toBe(4);

    expect(".o_form_sheet_bg > div > .o-form-buttonbox button:first-child").toHaveClass(
        "o_web_studio_add_element"
    );
    expect(queryAllAttributes(".o_form_sheet_bg > div > .o-form-buttonbox button", "name")).toEqual(
        [null, "one"]
    );
    expect(queryAllAttributes(".o_form_sheet_bg > .o-form-buttonbox button", "name")).toEqual([]);

    await contains(".o_web_studio_view").click();
    await contains(".o_web_studio_sidebar input#show_invisible").click();

    expect(".o_form_sheet_bg > div > .o-form-buttonbox button:first-child").toHaveClass(
        "o_web_studio_add_element"
    );
    expect(queryAllAttributes(".o_form_sheet_bg > div > .o-form-buttonbox button", "name")).toEqual(
        [null, "one", "two"]
    );
    expect(queryAllAttributes(".o_form_sheet_bg > .o-form-buttonbox button", "name")).toEqual([]);
});

test("button_box: many mixed buttons", async () => {
    Coucou._records = [{ id: 1 }];

    const editor = await mountViewEditor({
        type: "form",
        resModel: "coucou",
        resId: 1,
        arch: `<form>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button name="one" type="object" className="oe_stat_button" icon="fa-star">
                            <field name="id" widget="statinfo"/>
                        </button>
                        <button name="two" type="object" className="oe_stat_button" icon="fa-star">
                            <field name="id" widget="statinfo"/>
                        </button>
                        <button name="three" type="object" className="oe_stat_button" icon="fa-star" invisible="id != 5">
                            <field name="id" widget="statinfo"/>
                        </button>
                        <button name="four" type="object" className="oe_stat_button" icon="fa-star">
                            <field name="id" widget="statinfo"/>
                        </button>
                        <button name="five" type="object" className="oe_stat_button" icon="fa-star">
                            <field name="id" widget="statinfo"/>
                        </button>
                    </div>
                    <group><group><field name="id"/></group></group>
                </sheet>
            </form>`,
    });
    expect(editor.env.services.ui.size).toBe(4);

    expect(".o_form_sheet_bg > div > .o-form-buttonbox button:first-child").toHaveClass(
        "o_web_studio_add_element"
    );
    expect(queryAllAttributes(".o_form_sheet_bg > div > .o-form-buttonbox button", "name")).toEqual(
        [null, "one", "two", "four", "five"]
    );
    expect(queryAllAttributes(".o_form_sheet_bg > .o-form-buttonbox button", "name")).toEqual([]);

    await contains(".o_web_studio_view").click();
    await contains(".o_web_studio_sidebar input#show_invisible").click();

    expect(".o_form_sheet_bg > div > .o-form-buttonbox button:first-child").toHaveClass(
        "o_web_studio_add_element"
    );
    expect(queryAllAttributes(".o_form_sheet_bg > div > .o-form-buttonbox button", "name")).toEqual(
        [null, "one", "two", "three", null]
    );
    expect(queryAllAttributes(".o_form_sheet_bg > .o-form-buttonbox button", "name")).toEqual([]);
    expect(".o_form_sheet_bg > div > .o-form-buttonbox button:last-child").toHaveClass(
        "o_button_more"
    );

    await contains(".o-form-buttonbox .o_button_more").click();

    expect(".o_form_sheet_bg > div > .o-form-buttonbox button:first-child").toHaveClass(
        "o_web_studio_add_element"
    );
    expect(queryAllAttributes(".o_form_sheet_bg > div > .o-form-buttonbox button", "name")).toEqual(
        [null, "one", "two", "three", null]
    );
    expect(queryAllAttributes(".o_form_sheet_bg > .o-form-buttonbox button", "name")).toEqual([
        "four",
        "five",
    ]);
    expect(".o_form_sheet_bg > div > .o-form-buttonbox button:last-child").toHaveClass(
        "o_button_more"
    );
});

test("edit one2many form view (2 level) and check that the correct model is passed", async () => {
    expect.assertions(3);
    Product._fields.m2m = fields.Many2many({ relation: "product" });
    Coucou._records = [{ product_ids: [1] }];
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        resId: 1,
        arch: `
            <form>
                <sheet>
                    <field name="display_name"/>
                    <field name="product_ids">
                        <form>
                            <sheet>
                            <group>
                                <field name="m2m" widget='many2many_tags'/>
                            </group>
                            </sheet>
                        </form>
                    </field>
                </sheet>
            </form>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.model).toBe("product");
        expect(params.operations).toEqual([
            {
                type: "attributes",
                target: {
                    tag: "field",
                    attrs: {
                        name: "m2m",
                    },
                    xpath_info: [
                        {
                            tag: "form",
                            indice: 1,
                        },
                        {
                            tag: "sheet",
                            indice: 1,
                        },
                        {
                            tag: "group",
                            indice: 1,
                        },
                        {
                            tag: "field",
                            indice: 1,
                        },
                    ],
                    subview_xpath: "/form[1]/sheet[1]/field[2]/form[1]",
                },
                position: "attributes",
                node: {
                    tag: "field",
                    attrs: {
                        name: "m2m",
                        widget: "many2many_tags",
                        can_create: "true",
                        can_write: "true",
                    },
                },
                new_attrs: {
                    options: '{"no_create":true}',
                },
            },
        ]);
    });
    await contains(".o_web_studio_form_view_editor .o_field_one2many").click();
    await contains(
        ".o_web_studio_form_view_editor .o_field_one2many .o_web_studio_editX2Many[data-type='form']"
    ).click();
    await contains(".o_field_many2many_tags").click();
    await contains(".o_web_studio_sidebar_checkbox #no_create").click();
    expect.verifySteps(["edit_view"]);
});

test("display one2many without inline views", async () => {
    Product._views = {
        list: `<list><field name="toughness"/></list>`,
    };

    Coucou._views = {
        "form,1": `
            <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids' widget="one2many"/>
                </sheet>
            </form>`,
    };

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        viewId: 1,
    });

    onRpc("/web_studio/create_inline_view", async (request) => {
        expect.step("create_inline_view");
        const { params } = await request.json();
        const { model, field_name, subview_type, subview_xpath, view_id } = params;
        expect(model).toBe("product");
        expect(field_name).toBe("product_ids");
        expect(subview_type).toBe("list");
        expect(subview_xpath).toBe("/form[1]/sheet[1]/field[2]");
        expect(view_id).toBe(1);
        Coucou._views["form,1"] = `
            <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids'>${Product._views.list}</field>
                </sheet>
            </form>`;
        return editView(params, "list", Product._views.list);
    });

    expect(".o_field_one2many.o_field_widget").toHaveCount(1);

    await contains(".o_web_studio_view_renderer .o_field_one2many").click();
    await contains(
        ".o_web_studio_view_renderer .o_field_one2many .o_web_studio_editX2Many[data-type='list']"
    ).click();
    expect.verifySteps(["create_inline_view"]);
});

test("edit one2many list view", async () => {
    expect.assertions(13);

    serverState.debug = "1";

    Coucou._views["form,1"] = /* xml */ `
        <form>
            <sheet>
                <field name='display_name'/>
                <field name='product_ids'>
                    <list><field name='display_name'/></list>
                </field>
            </sheet>
        </form>`;
    Product._views["form,1"] = /* xml */ `
        <form />
    `;
    Product._fields.product_ids = fields.Many2many({ relation: "product" });

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        viewId: 1,
    });

    MockServer.env["ir.model.fields"]._views = {
        form: `<form><field name="model" /><field name="id" /></form>`,
    };

    MockServer.env["ir.model.fields"]._records = [{ id: 999 }];

    onRpc("ir.model.fields", "search_read", (params) => {
        expect(params.kwargs.domain).toEqual([
            ["model", "=", "product"],
            ["name", "=", "coucou_id"],
        ]);
        return [{ id: 999 }];
    });

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.view_id).toBe(1);
        expect(params.operations).toHaveLength(1);

        expect(params.operations[0].type).toBe("add");
        expect(params.operations[0].position).toBe("before");

        expect(params.operations[0].node).toEqual({
            tag: "field",
            attrs: {
                name: "coucou_id",
                optional: "show",
            },
        });

        expect(params.operations[0].target.attrs).toEqual({ name: "display_name" });
        expect(params.operations[0].target.tag).toBe("field");
        expect(params.operations[0].target.subview_xpath).toBe(
            "/form[1]/sheet[1]/field[2]/list[1]"
        );

        const newArch = /* xml */ `
            <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids'>
                        <list><field name='coucou_id'/><field name='display_name'/></list>
                    </field>
                </sheet>
            </form>`;
        return editView(params, "form", newArch);
    });

    await contains(".o_web_studio_view_renderer .o_field_one2many").click();
    expect(
        ".o_web_studio_view_renderer .o_field_one2many .o-web-studio-edit-x2manys-buttons"
    ).toHaveStyle({
        zIndex: "1000",
    });

    await contains(
        ".o_web_studio_view_renderer .o_field_one2many .o_web_studio_editX2Many"
    ).click();
    expect(".o_web_studio_view_renderer thead tr [data-studio-xpath]").toHaveCount(1);

    await contains(".o_web_studio_existing_fields_header").click();
    await contains(
        ".o_web_studio_existing_fields_section .o_web_studio_field_many2one"
    ).dragAndDrop(".o_web_studio_hook");
    await animationFrame();

    expect(".o_web_studio_view_renderer thead tr [data-studio-xpath]").toHaveCount(2);

    await contains(".o_web_studio_view_renderer [data-studio-xpath]").click();

    expect(".o_web_studio_sidebar .o_web_studio_parameters").toHaveCount(1);
    await contains(".o_web_studio_sidebar .o_web_studio_parameters").click();
});

test("edit one2many list view with widget fieldDependencies and some records", async () => {
    Product._fields.is_dep = fields.Char();
    Coucou._records = [{ product_ids: [1] }];
    Product._records = [{ is_dep: "the meters" }];
    Coucou._views = {
        "form,1": `<form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids'>
                        <list><field name='display_name' widget="withDependencies"/></list>
                    </field>
                </sheet>
            </form>`,
    };

    const charField = registry.category("fields").get("char");
    class CharWithDependencies extends charField.component {
        setup() {
            super.setup();
            const record = this.props.record;
            onMounted(() => {
                expect.step(["widget Dependency", record.fields.is_dep, record.data.is_dep]);
            });
        }
    }
    registry.category("fields").add("list.withDependencies", {
        ...charField,
        component: CharWithDependencies,
        fieldDependencies: [{ name: "is_dep", type: "char" }],
    });

    onRpc("fields_get", () => {
        expect.step("fields_get");
    });

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        viewId: 1,
        resId: 1,
    });

    expect.verifySteps([
        ["widget Dependency", { name: "is_dep", type: "char", readonly: true }, "the meters"],
    ]);

    expect(".o_web_studio_form_view_editor").toHaveCount(1);
    await contains(".o_field_one2many").click();
    await contains(".o_field_one2many .o_web_studio_editX2Many").click();

    expect.verifySteps([
        "fields_get",
        [
            "widget Dependency",
            {
                readonly: false,
                required: false,
                searchable: true,
                sortable: true,
                store: true,
                groupable: true,
                type: "char",
                string: "Is dep",
                name: "is_dep",
            },
            "the meters",
        ],
    ]);
    expect(".o_web_studio_list_view_editor").toHaveCount(1);
});

test("entering x2many with view widget", async () => {
    class MyWidget extends Component {
        static template = xml`<div class="myWidget" />`;
        static props = ["*"];
    }
    const myWidget = {
        component: MyWidget,
    };
    registry.category("view_widgets").add("myWidget", myWidget);
    Coucou._records = [{ product_ids: [1] }];
    Coucou._views = {
        "form,1": `
            <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids'>
                        <list><widget name="myWidget"/></list>
                    </field>
                </sheet>
            </form>`,
    };

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        viewId: 1,
        resId: 1,
    });

    expect(".o_web_studio_form_view_editor").toHaveCount(1);
    expect(".myWidget").toHaveCount(1);

    await contains(".o_web_studio_view_renderer .o_field_one2many").click();
    await contains(
        ".o_web_studio_view_renderer .o_field_one2many .o_web_studio_editX2Many[data-type='list']"
    ).click();

    expect(".o_web_studio_list_view_editor").toHaveCount(1);
    expect(".myWidget").toHaveCount(1);
});

test("edit one2many list view with list_view_ref context key", async () => {
    Coucou._records = [{ product_ids: [1] }];
    Coucou._views = {
        "form,1": `
            <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids' widget="one2many" context="{'list_view_ref': 'module.list_view_ref'}" />
                </sheet>
            </form>`,
    };
    Product._views = {
        "list,module.list_view_ref": `<list><field name="display_name"/></list>`,
    };

    onRpc("/web_studio/create_inline_view", async (request) => {
        const { params } = await request.json();
        expect.step("create_inline_view");
        const { context, model, field_name, subview_type, subview_xpath, view_id } = params;
        expect(context.list_view_ref).toEqual("module.list_view_ref");
        expect(model).toBe("product");
        expect(field_name).toBe("product_ids");
        expect(subview_type).toBe("list");
        expect(subview_xpath).toBe("/form[1]/sheet[1]/field[2]");
        expect(view_id).toBe(1);

        MockServer.env["coucou"]._views["form,1"] = `
            <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids'>${Product._views["list,module.list_view_ref"]}</field>
                </sheet>
            </form>`;
        return Product._views["list,module.list_view_ref"];
    });

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        viewId: 1,
        resId: 1,
    });

    await contains(".o_web_studio_view_renderer .o_field_one2many").click();
    await contains(
        ".o_web_studio_view_renderer .o_field_one2many .o_web_studio_editX2Many"
    ).click();
    expect.verifySteps(["create_inline_view"]);
});

test("navigate in nested x2many which has a context", async () => {
    Coucou._records = [{ id: 1 }];
    Coucou._views = {
        "form,1": `
            <form>
                <field name='product_ids'>
                    <form>
                        <div class="product-subview-form" />
                        <field name="partner_ids" context="{'context_key': 'value', 'parent': parent.id}">
                            <form>
                                <div class="po2m-subview-form" />
                                <field name="display_name" />
                            </form>
                        </field>
                    </form>
                </field>
            </form>`,
    };

    Product._views = {
        list: `<list><field name="display_name" /></list>`,
    };

    Partner._views = {
        list: `<list><field name="display_name" /></list>`,
    };

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        viewId: 1,
        resId: 1,
        context: { action_context_key: "couac" },
    });

    await contains(".o_web_studio_form_view_editor .o_field_one2many").click();
    await contains(
        ".o_web_studio_form_view_editor .o_field_one2many .o_web_studio_editX2Many[data-type='form']"
    ).click();

    expect(".o_view_controller .product-subview-form").toHaveCount(1);

    await contains(".o_web_studio_form_view_editor .o_field_one2many").click();
    await contains(
        ".o_web_studio_form_view_editor .o_field_one2many .o_web_studio_editX2Many[data-type='form']"
    ).click();

    expect(".o_view_controller .po2m-subview-form").toHaveCount(1);
});

test("navigate in x2many form which some field has a context", async () => {
    Coucou._records = [{ id: 1 }];
    Coucou._views = {
        "form,1": `
           <form>
                <field name='product_ids'>
                    <form>
                        <div class="product-subview-form" />
                        <field name="m2o_partner" context="{'context_key': 'value', 'parent': parent.id}" />
                    </form>
               </field>
           </form>`,
    };

    Product._views = {
        list: `<list><field name="display_name" /></list>`,
    };

    Partner._views = {
        list: `<list><field name="display_name" /></list>`,
    };

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        viewId: 1,
        resId: 1,
    });

    await contains(".o_web_studio_form_view_editor .o_field_one2many").click();
    await contains(
        ".o_web_studio_form_view_editor .o_field_one2many .o_web_studio_editX2Many[data-type='form']"
    ).click();

    expect(".o_view_controller .product-subview-form").toHaveCount(1);
});

test("navigate in x2many form which some field has a context -- context in action", async () => {
    Coucou._records = [{ id: 1 }];
    Coucou._views = {
        "form,1": `
           <form>
                <field name='product_ids'>
                    <form>
                        <div class="product-subview-form" />
                        <field name="m2o_partner" context="{'context_key': 'value', 'parent': parent.id}" />
                    </form>
               </field>
           </form>`,
    };

    Product._views = {
        list: `<list><field name="display_name" /></list>`,
    };

    Partner._views = {
        list: `<list><field name="display_name" /></list>`,
    };

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        viewId: 1,
        resId: 1,
        context: { action_context_key: "couac" },
    });

    await contains(".o_web_studio_form_view_editor .o_field_one2many").click();
    await contains(
        ".o_web_studio_form_view_editor .o_field_one2many .o_web_studio_editX2Many[data-type='form']"
    ).click();

    expect(".o_view_controller .product-subview-form").toHaveCount(1);
});

test("navigate in x2many form which some field has a context -- context in action with records in relation", async () => {
    Partner._records = [{ display_name: "couic" }];
    Product._records = [{ m2o_partner: 1 }];
    Coucou._records = [{ product_ids: [1] }];

    Coucou._views = {
        "form,1": `
           <form>
                <field name='product_ids'>
                    <form>
                        <div class="product-subview-form" />
                        <field name="m2o_partner" context="{'context_key': 'value', 'parent': parent.id}" />
                    </form>
               </field>
           </form>`,
    };

    Product._views = {
        list: `<list><field name="display_name" /></list>`,
    };

    Partner._views = {
        list: `<list><field name="display_name" /></list>`,
    };

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        viewId: 1,
        resId: 1,
        context: { action_context_key: "couac" },
    });

    await contains(".o_web_studio_form_view_editor .o_field_one2many").click();
    await contains(
        ".o_web_studio_form_view_editor .o_field_one2many .o_web_studio_editX2Many[data-type='form']"
    ).click();
    expect(".o_view_controller .product-subview-form").toHaveCount(1);
    expect(".o_field_many2one").toHaveText("couic");
});

test("navigate in x2many form which some field has a context -- with records in relation", async () => {
    Partner._records = [{ display_name: "couic" }];
    Product._records = [{ m2o_partner: 1 }];
    Coucou._records = [{ product_ids: [1] }];

    Coucou._views = {
        "form,1": `
            <form>
                <field name='product_ids'>
                    <form>
                        <div class="product-subview-form" />
                        <field name="m2o_partner" context="{'context_key': 'value', 'parent': parent.id}" />
                    </form>
                </field>
            </form>`,
    };

    Product._views = {
        list: `<list><field name="display_name" /></list>`,
    };

    Partner._views = {
        list: `<list><field name="display_name" /></list>`,
    };

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        viewId: 1,
        resId: 1,
    });

    await contains(".o_web_studio_form_view_editor .o_field_one2many").click();
    await contains(
        ".o_web_studio_form_view_editor .o_field_one2many .o_web_studio_editX2Many[data-type='form']"
    ).click();
    expect(".o_view_controller .product-subview-form").toHaveCount(1);
    expect(".o_field_many2one").toHaveText("couic");
});

test("navigate in x2many list which some field has a context -- with records in relation", async () => {
    Partner._records = [{ display_name: "couic" }];
    Product._records = [{ m2o_partner: 1 }];
    Coucou._records = [{ product_ids: [1] }];

    Coucou._views = {
        "form,1": `
            <form>
                <field name='product_ids'>
                    <list>
                        <field name="display_name" />
                        <field name="m2o_partner" context="{'context_key': 'value', 'parent': parent.id}" />
                    </list>
                </field>
            </form>`,
    };

    Product._views = {
        list: `<list><field name="display_name" /></list>`,
    };

    Partner._views = {
        list: `<list><field name="display_name" /></list>`,
    };

    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        viewId: 1,
        resId: 1,
    });

    await contains(".o_web_studio_form_view_editor .o_field_one2many").click();
    await contains(
        ".o_web_studio_form_view_editor .o_field_one2many .o_web_studio_editX2Many[data-type='list']"
    ).click();
    expect(".o_view_controller.o_list_view .o_data_row .o_list_many2one").toHaveText("couic");
});

test("x2many list with virtual record", async () => {
    handleDefaultStudioRoutes();
    Coucou._views = {
        "form,1": `
            <form>
                <field name='product_ids'>
                    <list>
                        <field name="display_name" />
                    </list>
               </field>
            </form>`,
    };

    onRpc("onchange", (params) => ({
        value: {
            product_ids: [
                [
                    0,
                    0,
                    {
                        display_name: "virtual",
                    },
                ],
            ],
        },
    }));

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        name: "coucouAction",
        res_model: "coucou",
        type: "ir.actions.act_window",
        views: [[1, "form"]],
    });
    await animationFrame();

    expect(".o_form_view .o_field_one2many .o_data_row").toHaveText("virtual");
    await openStudio();
    await contains(".o_web_studio_form_view_editor .o_field_one2many").click();
    await contains(
        ".o_web_studio_form_view_editor .o_field_one2many .o_web_studio_editX2Many[data-type='list']"
    ).click();

    expect(".o_view_controller.o_list_view").toHaveCount(1);
    expect(".o_data_row").toHaveCount(0);
});

test("Add tooltip support on the button", async () => {
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
        <header>
            <button string="Test" type="object" class="oe_highlight" title="Test"/>
        </header>
    </form>
    `,
    });
    await contains(".o_statusbar_buttons button").click();
    expect(".o_web_studio_sidebar .o_web_studio_property #title").toHaveValue("Test");
});

test("Change color on many2many tags", async () => {
    Product._fields.product_color = fields.Integer({ string: "Product Color" });
    Partner._fields.partner_color = fields.Integer({ string: "Partner Color" });

    await mountViewEditor({
        type: "form",
        resModel: "product",
        arch: /*xml*/ `
            <form>
                <sheet>
                    <group>
                        <field name="m2m_employees" widget="many2many_avatar_user"/>
                    </group>
                </sheet>
            </form>
        `,
    });
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect(params.operations[0].new_attrs).toEqual({
            options: '{"color_field":"partner_color"}',
        });
        const newArch = /* xml */ `
            <form>
                <sheet>
                    <group>
                        <field name="m2m_employees" widget="many2many_tags" options="{'color_field': 'partner_color'}"/>
                    </group>
                </sheet>
            </form>`;
        return editView(params, "form", newArch);
    });

    onRpc("partner", "fields_get", () => {
        expect.step("fields_get");
    });

    await contains(".o_form_label").click();
    await contains("input[name='color_field']").click();
    expect.verifySteps(["fields_get"]);
    expect(queryAllTexts(".dropdown-item")).toEqual(["Id", "Partner Color"]);
    await contains(".dropdown-item:contains('Partner Color')").click();
    expect("input[name='color_field']").toHaveValue("Partner Color");
    expect.verifySteps(["fields_get"]);
});

test("New button is active after adding it", async () => {
    onRpc("/web_studio/edit_view", (request) => {
        expect.step("edit_view");
        const newArch = `<form>
                <header>
                    <button name="1" type="action" invisible="1" string="First"/>
                    <button name="1" type="action" invisible="1" string="Second"/>
                    <t groups="some.group">
                        <button name="1" type="action" string="Third"/>
                    </t>
                    <button string="New button from studio" type="action"/>
                </header>
                <sheet>
                    <field name='display_name'/>
                </sheet>
            </form>
        `;
        return editView(request, "form", newArch);
    });
    await mountViewEditor({
        type: "form",
        resModel: "coucou",
        arch: `<form>
                <header>
                    <button name="1" type="action" invisible="1" string="First"/>
                    <button name="1" type="action" invisible="1" string="Second"/>
                    <t groups="some.group">
                        <button name="1" type="action" string="Third"/>
                    </t>
                </header>
                <sheet>
                    <field name='display_name'/>
                </sheet>
            </form>
        `,
    });

    expect(".o_web_studio_view_renderer .o_statusbar_buttons button").toHaveCount(2);
    await contains(
        ".o_web_studio_view_renderer .o_statusbar_buttons button.o-web-studio-editor--add-button-action"
    ).click();
    await waitFor(
        ".o_web_studio_sidebar:has(.o_web_studio_field_button) input[name=string]:value(New button from studio)"
    );
    expect.verifySteps(["edit_view"]);
    expect(".o_web_studio_view_renderer button:contains(New button from studio)").toHaveClass(
        "o-web-studio-editor--element-clicked"
    );
});
