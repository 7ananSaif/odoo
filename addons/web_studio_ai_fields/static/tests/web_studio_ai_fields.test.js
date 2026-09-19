import { AiPrompt, AiPromptDialog } from "@ai/ai_prompt/ai_prompt";
import { setSelection } from "@html_editor/../tests/_helpers/selection";
import { insertText } from "@html_editor/../tests/_helpers/user_actions";
import {
    contains,
    defineModels,
    fields,
    models,
    onRpc,
    patchWithCleanup,
    makeMockEnv,
} from "@web/../tests/web_test_helpers";
import { mountViewEditor } from "@web_studio/../tests/view_editor_tests_utils";

import { before, describe, expect, test } from "@odoo/hoot";
import { queryOne, waitFor } from "@odoo/hoot-dom";
import { registry } from "@web/core/registry";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";

describe.current.tags("desktop");

const serviceRegistry = registry.category("services");
const fakeAIChatLauncherService = {
    name: "aiChatLauncher",
    start() {
        return {};
    },
};
serviceRegistry.add("aiChatLauncher", fakeAIChatLauncherService, { force: true });

class Dummy extends models.Model {
    _name = "dummy";

    char = fields.Char({ ai: false });
    ai_char = fields.Char({ ai: "My prompt" });
    manual_char = fields.Char({ ai: false, manual: true });
}

class IrModel extends models.Model {
    _name = "ir.model";

    name = fields.Char();
    transient = fields.Boolean({ default: false });
    abstract = fields.Boolean({ default: false });

    _records = [
        { name: "mod1" },
        { name: "mod2", transient: true },
        { name: "mod2", abstract: true },
    ];
}

defineMailModels();
defineModels([Dummy, IrModel]);

test("ai and system prompt are readonly for base fields", async () => {
    before(() => {
        patchWithCleanup(AiPromptDialog.prototype, {
            setup() {
                super.setup();
                expect.step("ai_dialog");
            },
        });
    });
    onRpc("/web_studio/get_studio_view_arch", () => ({ studio_view_arch: "" }));
    const env = await makeMockEnv();
    await mountViewEditor({
        type: "form",
        resModel: "dummy",
        arch: `<form>
            <sheet>
                <field name="char"/>
                <field name="ai_char"/>
            </sheet>
        </form>
        `,
        env,
    });
    await contains(".o_field_char[name='char']").click();
    await waitFor(".o_web_studio_sidebar .o_web_studio_sidebar_checkbox input[name='AI']");
    expect(".o_web_studio_property input[name='AI']").toHaveAttribute("disabled");
    expect(".o_web_studio_property input[name='AI']").not.toBeChecked();
    expect(".o_web_studio_property div#ai_update_prompt").toHaveCount(0);
    await contains(".nav-link.o_web_studio_view").click();
    await contains(".o_field_char[name='ai_char']").click();
    await waitFor(".o_web_studio_sidebar .o_web_studio_sidebar_checkbox input[name='AI']");
    expect(".o_web_studio_property input[name='AI']").toHaveAttribute("disabled");
    expect(".o_web_studio_property input[name='AI']").toBeChecked();
    expect(".o_web_studio_property div#ai_update_prompt").toHaveCount(1);
    expect(".o_web_studio_property div#ai_update_prompt").toHaveText("My prompt");
    // click on prompt does not open the prompt edition dialog (no step)
    await contains(".o_web_studio_property input[name='AI']").click();
});

test("make custom field use ai", async () => {
    let promptEditor;
    let editCount = 0;
    before(() => {
        patchWithCleanup(AiPromptDialog.prototype, {
            setup() {
                super.setup();
                expect.step("ai_dialog");
            },
        });
        patchWithCleanup(AiPrompt.prototype, {
            onEditorLoad(editor) {
                promptEditor = editor;
                return super.onEditorLoad(...arguments);
            },
        });
    });
    onRpc("/web_studio/edit_field", async (request) => {
        const { params } = await request.json();
        expect.step("edit_field");
        editCount++;
        expect(params.field_name).toBe("manual_char");
        expect(params.model_name).toBe("dummy");
        if (editCount === 1) {
            expect(params.values.ai).toBe(true);
            return { system_prompt: "" };
        } else if (editCount === 2) {
            expect(params.values.system_prompt).toBe("<p>My prompt</p>");
        } else if (editCount === 3) {
            expect(params.values.ai).toBe(false);
        }
    });
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        if (editCount === 1) {
            expect(params.operations[0].new_attrs.widget).toBe("ai_char");
            return;
        } else if (editCount === 3) {
            expect(params.operations[1].new_attrs.widget).toBe("");
        }
        return;
    });
    const env = await makeMockEnv();
    await mountViewEditor({
        type: "form",
        resModel: "dummy",
        arch: `<form>
            <sheet>
                <field name="manual_char"/>
            </sheet>
        </form>
        `,
        env,
    });
    await contains(".o_field_char[name='manual_char']").click();
    await waitFor(".o_web_studio_sidebar .o_web_studio_sidebar_checkbox input[name='AI']");
    expect(".o_web_studio_property input[name='AI']").not.toHaveAttribute("disabled");
    expect(".o_web_studio_property input[name='AI']").not.toBeChecked();
    expect(".o_web_studio_property div#ai_update_prompt").toHaveCount(0);
    await contains(".o_web_studio_property input[name='AI']").check();
    expect.verifySteps(["edit_field", "edit_view"]);
    expect(".o_web_studio_property input[name='AI']").toBeChecked();
    expect(".o_web_studio_property div#ai_update_prompt").toHaveCount(1);
    await contains(".o_web_studio_property div#ai_update_prompt").click();
    expect.verifySteps(["ai_dialog"]);
    await waitFor(".o_ai_prompt_dialog");
    expect(".o_ai_prompt .odoo-editor-editable").toHaveText("");
    setSelection({ anchorNode: queryOne(".o_ai_prompt .odoo-editor-editable p") });
    await insertText(promptEditor, "My prompt");
    await contains(".modal-dialog footer .btn-primary").click();
    expect.verifySteps(["edit_field"]);
    // ensure default widget is used when removing ai
    await contains(".o_web_studio_property input[name='AI']").uncheck();
    expect.verifySteps(["edit_field", "edit_view"]);
});

test("insert ai field", async () => {
    let promptEditor;
    before(() => {
        patchWithCleanup(AiPrompt.prototype, {
            onEditorLoad(editor) {
                promptEditor = editor;
                return super.onEditorLoad(...arguments);
            },
        });
    });
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].node.field_description.type).toBe("char");
        expect(params.operations[0].node.field_description.ai).toBe(true);
        expect(params.operations[0].node.field_description.system_prompt).toBe(
            "<p>My prompt</p>",
        );
        expect(params.operations[0].node.attrs.widget).toBe("ai_char");
    });
    const env = await makeMockEnv();
    await mountViewEditor({
        type: "form",
        resModel: "dummy",
        arch: `<form>
            <group>
                <field name="char"/>
            </group>
        </form>
        `,
        env,
    });
    await contains(".o_web_studio_new_fields .o_web_studio_field_ai").dragAndDrop(
        ".o_inner_group .o_web_studio_hook:first-child",
    );
    // should open the ai field configuration dialog
    await waitFor(".o_web_studio_ai_field_configuration_dialog");
    // default type is text
    expect(".o_web_studio_ai_field_select_menu_toggler").toHaveText("Text");
    setSelection({ anchorNode: queryOne(".o_ai_prompt .odoo-editor-editable p") });
    await insertText(promptEditor, "My prompt");
    await contains(".o_web_studio_ai_field_configuration_dialog footer .btn-primary").click();
    expect.verifySteps(["edit_view"]);
});

test("insert selection ai field", async () => {
    let promptEditor;
    before(() => {
        patchWithCleanup(AiPrompt.prototype, {
            onEditorLoad(editor) {
                promptEditor = editor;
                return super.onEditorLoad(...arguments);
            },
        });
    });
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].node.field_description.type).toBe("selection");
        expect(params.operations[0].node.field_description.selection).toEqual([["val1", "val1"]]);
        expect(params.operations[0].node.field_description.ai).toBe(true);
        expect(params.operations[0].node.field_description.system_prompt).toBe(
            "<p>My prompt</p>",
        );
        expect(params.operations[0].node.attrs.widget).toBe("ai_selection");
    });
    const env = await makeMockEnv();
    await mountViewEditor({
        type: "form",
        resModel: "dummy",
        arch: `<form>
            <group>
                <field name="char"/>
            </group>
        </form>
        `,
        env,
    });
    await contains(".o_web_studio_new_fields .o_web_studio_field_ai").dragAndDrop(
        ".o_inner_group .o_web_studio_hook:first-child",
    );
    expect(
        ".o_web_studio_ai_field_configuration_dialog h5:contains('Selection Values')",
    ).toHaveCount(0);
    await contains(".o_web_studio_ai_field_select_menu_toggler").click();
    await contains(".o_web_studio_ai_field_select_menu_item.o_web_studio_field_selection").click();
    await waitFor("h5:contains('Selection Values')");
    await contains(
        ".o_web_studio_ai_field_configuration_dialog button:contains('Add Values')",
    ).click();
    await contains(".o_web_studio_selection_editor .o_web_studio_add_selection input").edit("val1");
    await contains(".o-web-studio-interactive-list-edit-item").click();
    await contains(".o_web_studio_selection_editor footer .btn-primary").click();
    await waitFor(".o_web_studio_ai_field_configuration_dialog .badge:contains('val1')");
    setSelection({ anchorNode: queryOne(".o_ai_prompt .odoo-editor-editable p") });
    await insertText(promptEditor, "My prompt");
    await contains(".o_web_studio_ai_field_configuration_dialog footer .btn-primary").click();
    expect.verifySteps(["edit_view"]);
});

test("insert relational ai field", async () => {
    let promptEditor;
    before(() => {
        patchWithCleanup(AiPrompt.prototype, {
            onEditorLoad(editor) {
                promptEditor = editor;
                return super.onEditorLoad(...arguments);
            },
        });
    });
    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].node.field_description.type).toBe("many2one");
        expect(params.operations[0].node.field_description.relation_id).toBe(1);
        expect(params.operations[0].node.field_description.ai).toBe(true);
        expect(params.operations[0].node.field_description.system_prompt).toBe(
            "<p>My prompt</p>",
        );
        expect(params.operations[0].node.attrs.widget).toBe("ai_many2one");
    });
    const env = await makeMockEnv();
    await mountViewEditor({
        type: "form",
        resModel: "dummy",
        arch: `<form>
            <group>
                <field name="char"/>
            </group>
        </form>
        `,
        env,
    });
    await contains(".o_web_studio_new_fields .o_web_studio_field_ai").dragAndDrop(
        ".o_inner_group .o_web_studio_hook:first-child",
    );
    // should open the ai field configuration dialog
    await waitFor(".o_web_studio_ai_field_configuration_dialog");
    expect(".o_web_studio_ai_field_configuration_dialog h5:contains('Relation')").toHaveCount(0);
    await contains(".o_web_studio_ai_field_select_menu_toggler").click();
    await contains(".o_web_studio_ai_field_select_menu_item.o_web_studio_field_many2one").click();
    await contains("h5:contains('Relation') + div .o_record_selector input").click();
    await waitFor(".o-autocomplete--dropdown-menu");
    // should only show models that are not abstract/transient.
    expect(".o-autocomplete .o-autocomplete--dropdown-item").toHaveCount(1);
    await contains(".o-autocomplete .o-autocomplete--dropdown-item").click();
    setSelection({ anchorNode: queryOne(".o_ai_prompt .odoo-editor-editable p") });
    await insertText(promptEditor, "My prompt");
    await contains(".o_web_studio_ai_field_configuration_dialog footer .btn-primary").click();
    expect.verifySteps(["edit_view"]);
});
