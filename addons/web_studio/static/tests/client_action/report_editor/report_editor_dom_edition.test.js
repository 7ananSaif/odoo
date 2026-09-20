import { setupEditor } from "@html_editor/../tests/_helpers/editor";
import { getContent } from "@html_editor/../tests/_helpers/selection";
import { insertText } from "@html_editor/../tests/_helpers/user_actions";
import { before, describe, expect, test } from "@odoo/hoot";
import {
    hover,
    manuallyDispatchProgrammaticEvent,
    press,
    queryAll,
    queryFirst,
    queryOne,
} from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { contains, defineModels, fields, models } from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";

import { getReportEditorPlugins } from "@web_studio/client_action/report_editor/report_editor_wysiwyg/editor_plugins/report_editor_plugin";

describe.current.tags("desktop");

class SomeModel extends models.Model {
    _name = "some.model";

    field = fields.Char({ string: "My little field" });
}

defineModels([SomeModel]);

before(() => {
    const services = registry.category("services");
    for (const [name] of services.getEntries()) {
        if (
            name.startsWith("mail.") ||
            name.startsWith("discuss.") ||
            ["bus.connection_alert", "bus.monitoring_service"].includes(name)
        ) {
            services.remove(name);
        }
    }
    services.remove("im_status");

    const main_components = registry.category("main_components");
    for (const [name] of main_components.getEntries()) {
        if (name.startsWith("mail.") || name.startsWith("discuss.") || name.startsWith("bus.")) {
            main_components.remove(name);
        }
    }
});

function getEditorOptions() {
    return {
        config: {
            Plugins: getReportEditorPlugins(),
            classList: ["odoo-editor-qweb"],
            reportResModel: "some.model",
        },
        props: {
            iframe: true,
            copyCss: true,
        },
    };
}

test("add column", async () => {
    const { editor } = await setupEditor(
        `<div style="width: 100px; margin-top: 50px; margin-left: 50px;">
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                    <q-th>HEAD2</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
                        <q-td>1[]</q-td>
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
                        <q-td>3</q-td>
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
                    <q-td>5</q-td>
                    <q-td>6</q-td>
                </q-tr>
            </q-tbody>
        </q-table></div>`,
        getEditorOptions()
    );

    await hover(queryFirst(":iframe q-th"));
    await contains(".o-overlay-container .o-we-table-menu").click();
    await contains(".o-dropdown-item:contains(Insert Right)").click();

    expect(getContent(editor.getElContent().firstElementChild)).toBe(`
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th><q-th><div><br></div></q-th>
                    <q-th>HEAD2</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
                        <q-td>1</q-td><q-td><div><br></div></q-td>
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
                        <q-td>3</q-td><q-td><div><br></div></q-td>
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
                    <q-td>5</q-td><q-td><div><br></div></q-td>
                    <q-td>6</q-td>
                </q-tr>
            </q-tbody>
        </q-table>`);
});

test("add column non-matching conditionals", async () => {
    const { editor } = await setupEditor(
        `<div style="width: 100px; margin-top: 50px; margin-left: 50px;">
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                    <q-th t-if="true">HEAD2</q-th>
                    <q-th t-else="">HEAD3</q-th>
                    <q-th>HEAD4</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <t t-if="true">
                    <q-tr>
                        <q-td>1</q-td>
                        <q-td>2</q-td>
                        <q-td>4</q-td>
                    </q-tr>
                </t>
                <t t-else="">
                    <q-tr>
                        <q-td>1</q-td>
                        <q-td>3</q-td>
                        <q-td>4</q-td>
                    </q-tr>
                </t>
            </q-tbody>
        </q-table></div>`,
        getEditorOptions()
    );

    await hover(queryFirst(":iframe q-th:last-child"));
    await contains(".o-overlay-container .o-we-table-menu").click();
    await contains(".o-dropdown-item:contains(Insert Right)").click();

    expect(getContent(editor.getElContent().firstElementChild)).toBe(`
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                    <q-th t-if="true">HEAD2</q-th>
                    <q-th t-else="">HEAD3</q-th>
                    <q-th>HEAD4</q-th><q-th><div><br></div></q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <t t-if="true">
                    <q-tr>
                        <q-td>1</q-td>
                        <q-td>2</q-td>
                        <q-td>4</q-td><q-td><div><br></div></q-td>
                    </q-tr>
                </t>
                <t t-else="">
                    <q-tr>
                        <q-td>1</q-td>
                        <q-td>3</q-td>
                        <q-td>4</q-td><q-td><div><br></div></q-td>
                    </q-tr>
                </t>
            </q-tbody>
        </q-table>`);
});

test("remove column", async () => {
    const { editor } = await setupEditor(
        `<div style="width: 100px; margin-top: 50px; margin-left: 50px;">
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                    <q-th>HEAD2</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
                        <q-td>1[]</q-td>
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
                        <q-td>3</q-td>
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
                    <q-td>5</q-td>
                    <q-td>6</q-td>
                </q-tr>
            </q-tbody>
        </q-table></div>`,
        getEditorOptions()
    );
    await hover(queryFirst(":iframe q-th"));
    await contains(".o-overlay-container .o-we-table-menu").click();
    await contains(".o-dropdown-item:contains(Delete)").click();

    const el = editor.getElContent();
    expect(getContent(el.firstElementChild)).toBe(`
        <q-table>
            <q-thead>
                <q-tr>
${"                    "}
                    <q-th>HEAD2</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
${"                        "}
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
${"                        "}
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
${"                    "}
                    <q-td>6</q-td>
                </q-tr>
            </q-tbody>
        </q-table>`);
});

test("remove column colspan", async () => {
    const { editor, el } = await setupEditor(
        `<div style="width: 100px; margin-top: 50px; margin-left: 50px;">
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                    <q-th>HEAD2</q-th>
                    <q-th>HEAD3</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
                        <q-td colspan="2">1[]</q-td>
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
                        <q-td colspan="2">3</q-td>
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
                    <q-td>5</q-td>
                    <q-td colspan="2">6</q-td>
                </q-tr>
            </q-tbody>
        </q-table></div>`,
        getEditorOptions()
    );

    expect(getContent(el.querySelector("div"))).toBe(`
        <q-table class="oe_unbreakable" style="--q-table-col-count: 3;">
            <q-thead class="oe_unbreakable">
                <q-tr class="oe_unbreakable">
                    <q-th class="oe_unbreakable">HEAD1</q-th>
                    <q-th class="oe_unbreakable">HEAD2</q-th>
                    <q-th class="oe_unbreakable">HEAD3</q-th>
                </q-tr>
            </q-thead>
            <q-tbody class="oe_unbreakable">
                <q-tr class="oe_unbreakable">
                    <t t-if="true" data-oe-t-inline="true" data-oe-t-group="0" data-oe-t-selectable="true" data-oe-t-group-active="true">
                        <q-td colspan="2" class="oe_unbreakable" style="--q-cell-col-size: 2;">1[]</q-td>
                        <q-td class="oe_unbreakable">2</q-td>
                    </t>
                    <t t-else="" data-oe-t-inline="true" data-oe-t-selectable="true" data-oe-t-group="0">
                        <q-td colspan="2" class="oe_unbreakable" style="--q-cell-col-size: 2;">3</q-td>
                        <q-td class="oe_unbreakable">4</q-td>
                    </t>
                </q-tr>
                <q-tr class="oe_unbreakable">
                    <q-td class="oe_unbreakable">5</q-td>
                    <q-td colspan="2" class="oe_unbreakable" style="--q-cell-col-size: 2;">6</q-td>
                </q-tr>
            </q-tbody>
        </q-table>`);

    await hover(queryAll(":iframe q-th")[1]);
    await contains(".o-overlay-container .o-we-table-menu").click();
    await contains(".o-dropdown-item:contains(Delete)").click();

    const cleanedEl = editor.getElContent();
    expect(getContent(cleanedEl.firstElementChild)).toBe(`
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
${"                    "}
                    <q-th>HEAD3</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
                        <q-td>1</q-td>
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
                        <q-td>3</q-td>
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
                    <q-td>5</q-td>
                    <q-td>6</q-td>
                </q-tr>
            </q-tbody>
        </q-table>`);
});

test("move outside table menu must remove it if the menu is close", async () => {
    await setupEditor(
        `<div style="width: 100px; margin-top: 50px; margin-left: 50px;">
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                    <q-th>HEAD2</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
                        <q-td>1[]</q-td>
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
                        <q-td>3</q-td>
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
                    <q-td>5</q-td>
                    <q-td>6</q-td>
                </q-tr>
            </q-tbody>
        </q-table></div>`,
        getEditorOptions()
    );

    await hover(queryAll(":iframe q-th")[1]);
    await animationFrame();
    expect(".o-overlay-container .o-we-table-menu").toHaveCount(1);

    await hover(":iframe q-table");
    await animationFrame();
    expect(".o-overlay-container .o-we-table-menu").toHaveCount(0);
});

test("move outside table menu shouldn't remove it if the menu is close, we should click to close it", async () => {
    await setupEditor(
        `<div style="width: 100px; margin-top: 50px; margin-left: 50px;">
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                    <q-th>HEAD2</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
                        <q-td>1[]</q-td>
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
                        <q-td>3</q-td>
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
                    <q-td>5</q-td>
                    <q-td>6</q-td>
                </q-tr>
            </q-tbody>
        </q-table></div>`,
        getEditorOptions()
    );

    await hover(queryAll(":iframe q-th")[1]);
    await animationFrame();
    expect(".o-overlay-container .o-we-table-menu").toHaveCount(1);
    expect(".o-dropdown-item").toHaveCount(0);

    await contains(".o-overlay-container .o-we-table-menu").click();
    expect(".o-overlay-container .o-we-table-menu").toHaveCount(1);
    expect(".o-dropdown-item").toHaveCount(3);

    await hover(":iframe q-table");
    await animationFrame();
    expect(".o-overlay-container .o-we-table-menu").toHaveCount(1);
    expect(".o-dropdown-item").toHaveCount(3);

    await contains(":iframe q-table").click();
    await animationFrame();
    expect(".o-overlay-container .o-we-table-menu").toHaveCount(0);
    expect(".o-dropdown-item").toHaveCount(0);
});

test("push and remove readable expression as text node", async () => {
    const { editor, el } = await setupEditor(
        `<div>a<span t-field="doc.field" data-oe-expression-readable="human > expr"></span></div>`,
        getEditorOptions()
    );
    expect(getContent(el)).toBe(
        `<div class="o-paragraph">a<span t-field="doc.field" data-oe-expression-readable="human > expr" data-oe-protected="true" contenteditable="false">human > expr</span></div>`
    );

    expect(getContent(editor.getElContent())).toBe(
        '<div>a<span t-field="doc.field" data-oe-expression-readable="human > expr"></span></div>'
    );
});

test("select all t-field", async () => {
    const { el } = await setupEditor(
        `<div>a<span t-field="doc.field" data-oe-expression-readable="human > expr"></span></div>`,
        getEditorOptions()
    );
    await contains(":iframe span[t-field]").click();
    expect(getContent(el)).toBe(
        `<div class="o-paragraph">a[<span t-field="doc.field" data-oe-expression-readable="human > expr" data-oe-protected="true" contenteditable="false">human > expr</span>]</div>`
    );
});

test("copy t-field", async () => {
    const options = getEditorOptions();
    // Disable iframe for now: seems that hoot.press doesn't properly handle it.
    options.props.iframe = false;

    const { editor, el } = await setupEditor(
        `<div>a<span t-field="doc.field" data-oe-expression-readable="human ... expr"></span></div>`,
        options
    );
    await contains("span[t-field]").click();
    const clipboardData = new DataTransfer();
    await press(["ctrl", "c"], { dataTransfer: clipboardData });
    expect(clipboardData.getData("application/vnd.odoo.odoo-editor")).toBe(
        `<div><span t-field="doc.field" data-oe-expression-readable="human ... expr" data-oe-protected="true" contenteditable="false"></span></div>`
    );

    editor.shared.selection.setSelection({ anchorNode: queryOne(".odoo-editor-editable div") });
    await manuallyDispatchProgrammaticEvent(el, "paste", { clipboardData });

    expect(getContent(el)).toBe(
        `<div class="o-paragraph"><span contenteditable="false" data-oe-protected="true" data-oe-expression-readable="human ... expr" t-field="doc.field">human ... expr</span>[]a<span t-field="doc.field" data-oe-expression-readable="human ... expr" data-oe-protected="true" contenteditable="false">human ... expr</span></div>`
    );
});

test("disable formatting stuff on t-att-class and t-att-style (and their format counterparts", async () => {
    await setupEditor(
        `<div>a<span t-field="doc.field" data-oe-expression-readable="human > expr" t-att-class="expr_class"></span></div>`,
        getEditorOptions()
    );
    await contains(":iframe span[t-field]").click();
    await contains(".o-we-toolbar [name=expand_toolbar]").click();
    const allDisabled = queryAll(".o-we-toolbar button:disabled");
    expect(allDisabled.map((el) => el.title)).toEqual([
        "Select font style",
        "Select font size",
        "Toggle bold",
        "Toggle italic",
        "Toggle underline",
        "Apply Font Color",
        "Add a link",
    ]);
});

test("add t-field", async () => {
    const oeContext = JSON.stringify({
        docs: {
            model: "some.model",
            name: "Some Model",
        },
        doc: {
            model: "some.model",
            name: "Some Model",
        },
    });

    const { editor, el } = await setupEditor(
        `<div oe-context='${oeContext}' ws-view-id="1" t-foreach="docs" t-as="doc">[hop hop]</div>`,
        getEditorOptions()
    );
    await insertText(editor, "/");
    await contains(".o-we-powerbox .o-we-command-name:text(Field)").click();

    await contains(
        ".o-web-studio-report-dynamic-placeholder-popover .o_model_field_selector_value"
    ).click();
    await contains(".o_model_field_selector_popover_page li[data-name='field'] button").click();
    expect(
        ".o-web-studio-report-dynamic-placeholder-popover input[name='label_value']"
    ).toHaveValue("My little field");

    await contains(".o-web-studio-report-dynamic-placeholder-popover button.btn-primary").click();
    expect(getContent(el.querySelector("div"))).toBe(
        '<span data-oe-expression-readable="My little field" data-oe-demo="My little field" t-field="doc.field" data-oe-protected="true" contenteditable="false">My little field</span>[]'
    );
});

test("edit t-field and back", async () => {
    const oeContext = JSON.stringify({
        doc: {
            model: "some.model",
            name: "Some Model",
        },
    });

    const { editor, el } = await setupEditor(
        `<div oe-context='${oeContext}' ws-view-id="1">a<span t-field="doc.field" data-oe-expression-readable="human > expr" data-oe-demo="demo brol"></span></div>`,
        getEditorOptions()
    );
    expect(getContent(el)).toBe(
        `<div oe-context='${oeContext}' ws-view-id="1" class="o-paragraph">a<span t-field="doc.field" data-oe-expression-readable="human > expr" data-oe-demo="demo brol" data-oe-protected="true" contenteditable="false">demo brol</span></div>`
    );

    await contains(":iframe span[t-field]").click();
    await contains(".o-we-toolbar button[name='editDynamicField']").click();
    await contains(
        ".o-web-studio-report-dynamic-placeholder-popover .o_model_field_selector_value"
    ).click();
    await contains(
        ".o_model_field_selector_popover_page li[data-name='display_name'] button"
    ).click();
    await contains(
        ".o-web-studio-report-dynamic-placeholder-popover input[name='label_value']"
    ).edit("edited", { confirm: false });
    await contains(".o-web-studio-report-dynamic-placeholder-popover button.btn-primary").click();

    expect(getContent(el)).toBe(
        `<div oe-context='${oeContext}' ws-view-id="1" class="o-paragraph o_dirty">a[<span t-field="doc.display_name" data-oe-expression-readable="Display name" data-oe-demo="edited" data-oe-protected="true" contenteditable="false">edited</span>]</div>`
    );

    expect(getContent(editor.getElContent())).toBe(
        `<div oe-context='${oeContext}' ws-view-id="1" class="o_dirty">a<span t-field="doc.display_name" data-oe-expression-readable="Display name" data-oe-demo="edited"></span></div>`
    );

    editor.shared.history.undo();
    await animationFrame();
    expect(getContent(el)).toBe(
        `<div oe-context='${oeContext}' ws-view-id="1" class="o-paragraph o_dirty">[]a<span t-field="doc.field" data-oe-expression-readable="human > expr" data-oe-demo="demo brol" data-oe-protected="true" contenteditable="false">demo brol</span></div>`
    );
});
