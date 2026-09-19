import { setupEditor } from "@html_editor/../tests/_helpers/editor";
import { getContent } from "@html_editor/../tests/_helpers/selection";
import { deleteBackward } from "@html_editor/../tests/_helpers/user_actions";
import { MAIN_PLUGINS } from "@html_editor/plugin_sets";
import { KnowledgeDeleteFirstLinePlugin } from "@knowledge/editor/plugins/delete_first_line_plugin/delete_first_line_plugin";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { test, expect } from "@odoo/hoot";

function getConfig() {
    return {
        Plugins: [...MAIN_PLUGINS, KnowledgeDeleteFirstLinePlugin],
    };
}

defineMailModels();

test("deleteBackward on the first line of an article", async () => {
    const { editor, el } = await setupEditor(`<p>[]<br></p><p>content</p>`, {
        config: getConfig(),
    });
    deleteBackward(editor);
    expect(getContent(el)).toBe(`<p>[]content</p>`);
});
