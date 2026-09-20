import { defineKnowledgeModels } from "@knowledge/../tests/knowledge_test_helpers";
import { click, contains } from "@mail/../tests/mail_test_helpers";
import { beforeEach, describe, test } from "@odoo/hoot";
import {
    asyncStep,
    mountView,
    onRpc,
    serverState,
    waitForSteps,
} from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
defineKnowledgeModels();

beforeEach(() => {
    onRpc("knowledge.article", "get_user_sorted_articles", () => []);
    onRpc("knowledge.article", "has_access", () => true);
    onRpc("res.partner", "web_save", () => asyncStep("save"));
});

test("can search for article on existing record", async () => {
    await mountView({
        type: "form",
        resModel: "res.partner",
        resId: serverState.partnerId,
    });
    await contains(".o_control_panel_navigation .o_knowledge_icon_search");
    await contains(".o_command_palette", { count: 0 });

    await click(".o_control_panel_navigation .o_knowledge_icon_search");
    await contains(".o_command_palette");
    await waitForSteps([]);
});

test("can search for article when creating valid record", async () => {
    await mountView({
        type: "form",
        resModel: "res.partner",
    });
    await contains(".o_control_panel_navigation .o_knowledge_icon_search");
    await contains(".o_command_palette", { count: 0 });

    await click(".o_control_panel_navigation .o_knowledge_icon_search");
    await contains(".o_command_palette");
    await waitForSteps(["save"]);
});

test("cannot search for article when creating invalid record", async () => {
    await mountView({
        type: "form",
        resModel: "res.partner",
        arch: /* xml */ `
            <form string="Partners">
                <sheet>
                    <field name="name" required="1" />
                </sheet>
                <chatter/>
            </form>
        `,
    });
    await contains(".o_control_panel_navigation .o_knowledge_icon_search");
    await contains(".o_command_palette", { count: 0 });

    await click(".o_control_panel_navigation .o_knowledge_icon_search");
    await contains(".o_command_palette", { count: 0 });
    await waitForSteps([]);
});
