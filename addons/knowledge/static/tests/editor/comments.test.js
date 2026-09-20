import { before, describe, expect, test } from "@odoo/hoot";
import { manuallyDispatchProgrammaticEvent } from "@odoo/hoot-dom";
import { setupEditor } from "@html_editor/../tests/_helpers/editor";
import { unformat } from "@html_editor/../tests/_helpers/format";
import { getContent } from "@html_editor/../tests/_helpers/selection";
import { execCommand } from "@html_editor/../tests/_helpers/userCommands";
import { MAIN_PLUGINS } from "@html_editor/plugin_sets";
import { Wysiwyg } from "@html_editor/wysiwyg";
import { mockKnowledgeCommentsService } from "@knowledge/../tests/knowledge_test_helpers";
import { KnowledgeCommentsPlugin } from "@knowledge/editor/plugins/comments_plugin/comments_plugin";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";

function getCommentsConfig() {
    return {
        Plugins: [...MAIN_PLUGINS, KnowledgeCommentsPlugin],
        onLayoutGeometryChange: () => {},
    };
}
defineMailModels();

describe("knowledge comments", () => {
    before(() => {
        mockKnowledgeCommentsService();
        patchWithCleanup(Wysiwyg.prototype, {
            getEditorConfig() {
                const config = super.getEditorConfig();
                config.localOverlayContainers.key = "test_comments";
                return config;
            },
        });
        patchWithCleanup(registry.category("test_comments"), {
            // prevent the knowledge comments handler from spawning.
            add: () => {},
        });
    });
    test("should insert knowledge comments beacon around selected content and add feffs around it.", async () => {
        const { el, editor } = await setupEditor(`<p>a[bc]d</p>`, {
            config: getCommentsConfig(),
        });
        execCommand(editor, "addComments");
        // Validate that there is only one \ufeff inside knowledge comments beacons
        // (instead of 2 for a normal link)
        expect(getContent(el)).toBe(
            unformat(
                `<p>
                    a\ufeff<a class="oe_unremovable oe_thread_beacon" data-oe-protected="true" contenteditable="false" data-id="undefined" data-oe-type="threadBeaconStart" data-oe-model="knowledge.article" data-peer-id="">
                        \ufeff
                    </a>\ufeff[]bc\ufeff<a class="oe_unremovable oe_thread_beacon" data-oe-protected="true" contenteditable="false" data-id="undefined" data-oe-type="threadBeaconEnd" data-oe-model="knowledge.article" data-peer-id="">
                        \ufeff
                    </a>\ufeffd
                </p>`
            )
        );
        // This operation will induce a normalization involving a common ancestor of
        // knowledge comment anchors, and the following step makes sure that the
        // normalization in this complex case (split a node) produces the desired
        // `\ufeff` configuration.
        await manuallyDispatchProgrammaticEvent(el, "beforeinput", {
            inputType: "insertParagraph",
        });
        // Validate that there is only one \ufeff inside knowledge comments beacons
        // (instead of 3 if we allowed 2 at the previous step, because the anchor has no content)
        expect(getContent(el)).toBe(
            unformat(
                `<p>
                    a\ufeff<a class="oe_unremovable oe_thread_beacon" data-oe-protected="true" contenteditable="false" data-id="undefined" data-oe-type="threadBeaconStart" data-oe-model="knowledge.article" data-peer-id="">
                        \ufeff
                    </a>\ufeff
                </p>
                <p>
                    []bc\ufeff<a class="oe_unremovable oe_thread_beacon" data-oe-protected="true" contenteditable="false" data-id="undefined" data-oe-type="threadBeaconEnd" data-oe-model="knowledge.article" data-peer-id="">
                        \ufeff
                    </a>\ufeffd
                </p>`
            )
        );
    });
});
