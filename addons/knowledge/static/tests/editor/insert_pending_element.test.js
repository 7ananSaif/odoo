import { setupEditor } from "@html_editor/../tests/_helpers/editor";
import { getContent } from "@html_editor/../tests/_helpers/selection";
import { Editor } from "@html_editor/editor";
import { MAIN_PLUGINS } from "@html_editor/plugin_sets";
import { InsertPendingElementPlugin } from "@knowledge/editor/plugins/insert_pending_element_plugin/insert_pending_element_plugin";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { before, test, expect } from "@odoo/hoot";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";

function getConfig() {
    return {
        Plugins: [...MAIN_PLUGINS, InsertPendingElementPlugin],
    };
}

function createPendingBlock() {
    const block = document.createElement("div");
    block.classList.add("oe_unbreakable");
    block.append(document.createTextNode("coucou"));
    return block;
}

function prepareBlueprint(blueprint) {
    before(() => {
        patchWithCleanup(Editor.prototype, {
            startPlugins() {
                this.config.getRecordInfo = () => ({
                    resModel: "dummyModel",
                    resId: 1,
                });
                this.services.knowledgeCommandsService.setPendingEmbeddedBlueprint({
                    embeddedBlueprint: blueprint,
                    model: "dummyModel",
                    resId: 1,
                    field: "body",
                });
                super.startPlugins();
            },
        });
    });
}

defineMailModels();

test("insert pending inline", async () => {
    prepareBlueprint(document.createTextNode("coucou"));
    const { el } = await setupEditor(`<p>content</p>`, {
        config: getConfig(),
    });
    expect(getContent(el)).toBe(`<p>content</p><p>coucou[]</p>`);
});

test("insert pending block in empty article", async () => {
    prepareBlueprint(createPendingBlock());
    const { el } = await setupEditor(`<p>[]<br></p>`, {
        config: getConfig(),
    });
    expect(getContent(el)).toBe(
        `<p data-selection-placeholder=""><br></p><div class="oe_unbreakable">coucou</div><p o-we-hint-text='Type "/" for commands' class="o-we-hint">[]<br></p>`
    );
});

test("insert pending block in non-empty article", async () => {
    prepareBlueprint(createPendingBlock());
    const { el } = await setupEditor(`<p>[]<br></p><p>content</p>`, {
        config: getConfig(),
    });
    expect(getContent(el)).toBe(
        `<p><br></p><p>content</p><div class="oe_unbreakable">coucou</div><p o-we-hint-text='Type "/" for commands' class="o-we-hint">[]<br></p>`
    );
});
