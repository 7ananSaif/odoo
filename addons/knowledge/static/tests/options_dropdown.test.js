import { OptionsDropdown } from "@knowledge/components/options_dropdown/options_dropdown";
import { knowledgeTopbar } from "@knowledge/components/topbar/topbar";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import {
    asyncStep,
    contains,
    defineModels,
    fields,
    getKwArgs,
    getMockEnv,
    makeMockServer,
    mockService,
    models,
    mountView,
    onRpc,
    patchWithCleanup,
    waitForSteps,
} from "@web/../tests/web_test_helpers";
import { serializeDateTime } from "@web/core/l10n/dates";
import { user } from "@web/core/user";

import { expect, test } from "@odoo/hoot";
import { click, runAllTimers, waitFor } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";

class KnowledgeArticle extends models.ServerModel {
    _name = "knowledge.article";

    category = fields.Generic({ default: "private" });
    user_can_write = fields.Generic({ default: true });
    user_has_access = fields.Generic({ default: true });
    last_edition_date = fields.Datetime({
        string: "Last Modified on",
        default: (record) => record.create_date,
    });
    last_edition_uid = fields.Many2one({ relation: "res.users" });
    article_properties_definition = fields.Generic({ default: [] });

    action_send_to_trash(ids) {
        this.write(ids, { active: false, to_delete: true });
    }

    action_set_lock() {
        const kwargs = getKwArgs(arguments, "ids", "lock");
        this.write(kwargs.ids, { is_locked: kwargs.lock });
    }

    get_sidebar_articles() {
        return {
            articles: this._filter(),
            favorite_ids: [],
        };
    }

    has_access = function () {
        return Promise.resolve(true);
    };
}

class KnowledgeArticleThread extends models.ServerModel {}
class KnowledgeCover extends models.ServerModel {}

defineMailModels();
defineModels([KnowledgeArticle, KnowledgeArticleThread, KnowledgeCover]);

async function mountTopbar(articleId) {
    patchWithCleanup(knowledgeTopbar, {
        fieldDependencies: [
            ...knowledgeTopbar.fieldDependencies.map((dependency) => ({
                ...dependency,
                readonly: false,
            })),
            { name: "create_date", type: "datetime" },
            { name: "last_edition_date", type: "datetime" },
            { name: "html_field_history_metadata", type: "jsonb" },
        ],
    });
    await mountView({
        arch: /* xml */ `
            <form js_class="knowledge_article_view_form">
                <widget name="knowledge_topbar"/>
            </form>
        `,
        resModel: "knowledge.article",
        resId: articleId,
        type: "form",
    });
    await waitFor(".o_knowledge_form_view");
}

async function openOptionsDropdown() {
    await click(".o_knowledge_header .dropdown-toggle[title='More actions']");
    await waitFor(".o_knowledge_options_dropdown");
    await animationFrame();
}

async function waitForOptionsDropdownClose() {
    await waitFor(".o-overlay-container:not(:has(.o_knowledge_options_dropdown))");
    await animationFrame();
}

function assertOptionsDropdown(config) {
    const { canWrite, hasParent, isInternalUser, isLocked } = config;
    expect(".dropdown-item:contains('Add Icon')").toHaveCount(canWrite && !isLocked ? 1 : 0);
    expect(".dropdown-item:contains('Add Cover')").toHaveCount(
        canWrite && isInternalUser && !isLocked ? 1 : 0
    );
    expect(".dropdown-item:not(.o_disabled_option):contains('Add Properties')").toHaveCount(
        canWrite && !isLocked && hasParent ? 1 : 0
    );
    expect(".dropdown-item:contains('Full Width')").toHaveCount(canWrite ? 1 : 0);
    expect(".dropdown-item:contains('Move To')").toHaveCount(canWrite && isInternalUser ? 1 : 0);
    expect(".dropdown-item:contains('Lock Content')").toHaveCount(canWrite && !isLocked ? 1 : 0);
    expect(".dropdown-item:contains('Create a Copy')").toHaveCount(1);
    expect(".dropdown-item:contains('Convert into Article Item')").toHaveCount(
        hasParent && canWrite ? 1 : 0
    );
    expect(".dropdown-item:contains('Download PDF')").toHaveCount(1);
    expect(".dropdown-item:contains('Add to Templates')").toHaveCount(
        canWrite && isInternalUser ? 1 : 0
    );
    expect(".dropdown-item:contains('Send to Trash')").toHaveCount(
        canWrite && isInternalUser ? 1 : 0
    );
}

test("Options Dropdown layout for a readonly article", async () => {
    const mockServer = await makeMockServer();
    const articleId = mockServer.env["knowledge.article"].create({ user_can_write: false });
    await mountTopbar(articleId);
    await openOptionsDropdown();
    // user with read permission can only copy and export the article and see create and edit info
    assertOptionsDropdown({ isInternalUser: true });
    expect(".o_knowledge_options_dropdown div.text-muted:contains('Last Edited')").toHaveCount(1);
});

test("Options Dropdown layout for a portal user", async () => {
    patchWithCleanup(user, { hasGroup: (group) => group !== "base.group_user" }); // portal user
    const mockServer = await makeMockServer();
    const articleId = mockServer.env["knowledge.article"].create({});
    await mountTopbar(articleId);
    await openOptionsDropdown();
    // some options are not shown for portal users
    expect(".o_knowledge_options_dropdown .dropdown-item").toHaveCount(6);
    assertOptionsDropdown({ canWrite: true, isInternalUser: false });
    expect(".o_knowledge_options_dropdown div.text-muted:contains('Last Edited')").toHaveCount(1);
});

test("Add/Remove Cover", async () => {
    let addRandomCoverShouldFail = false;
    const mockServer = await makeMockServer();
    const articleId = mockServer.env["knowledge.article"].create({ name: "Bloups" });
    onRpc(`/knowledge/article/${articleId}/add_random_cover`, async (request) => {
        if (addRandomCoverShouldFail) {
            return { error: "error" };
        }
        const { params } = await request.json();
        expect(params.orientation).toBe("landscape");
        expect(params.query).toBe("Bloups");
        asyncStep("add random cover");
        return { cover_id: mockServer.env["knowledge.cover"].create({}) };
    });
    await mountTopbar(articleId);
    await openOptionsDropdown();
    expect(".dropdown-item:contains('Remove Cover')").toHaveCount(0);
    await click(".dropdown-item:contains('Add Cover')");
    await waitForOptionsDropdownClose();
    await waitForSteps(["add random cover"]);
    await openOptionsDropdown();
    expect(".dropdown-item:contains('Add Cover')").toHaveCount(0);
    await click(".dropdown-item:contains('Remove Cover')");
    await waitForOptionsDropdownClose();

    addRandomCoverShouldFail = true;

    await openOptionsDropdown();
    expect(".dropdown-item:contains('Remove Cover')").toHaveCount(0);
    await click(".dropdown-item:contains('Add Cover')");
    // request failed (eg. unsplash key missing), should fallback to cover selector
    await waitFor(".o_select_media_dialog");
    // search should be populated with article name
    expect(".o_select_media_dialog input.o_we_search").toHaveValue("Bloups");
});

test("Add Properties", async () => {
    const mockServer = await makeMockServer();
    const parentId = mockServer.env["knowledge.article"].create({ name: "p" });
    mockServer.env["knowledge.article"].create({ name: "c", parent_id: parentId });
    localStorage.setItem("knowledge.unfolded.ids", parentId); // show article in sidebar
    await mountTopbar(parentId);
    // add properties button should be disabled on root articles
    await openOptionsDropdown();
    expect(".dropdown-item:contains('Add Properties')").toHaveClass("o_disabled_option");
    if (getMockEnv().isSmall) {
        await click(".o_bottom_sheet_backdrop");
    }
    await click(".o_article_name:contains('c')");
    await waitFor(".o_article_active .o_article_name:contains('c')");
    // add properties shouldn't be disabled anymore
    await openOptionsDropdown();
    expect(".dropdown-item:contains('Add Properties')").not.toHaveClass("o_disabled_option");
    await click(".dropdown-item:contains('Add Properties')");
    await waitForOptionsDropdownClose();
    // add properties button shouldn't be shown anymore
    await openOptionsDropdown();
    expect(".dropdown-item:contains('Add Properties')").toHaveCount(0);
    if (getMockEnv().isSmall) {
        await click(".o_bottom_sheet_backdrop");
    }
    // add properties button should be shown after closing the properties (no property created)
    await click(".o_knowledge_header .btn-properties");
    await openOptionsDropdown();
    expect(".dropdown-item:contains('Add Properties')").not.toHaveClass("o_disabled_option");
});

test("Toggle lock", async () => {
    const mockServer = await makeMockServer();
    const articleId = mockServer.env["knowledge.article"].create({});
    await mountTopbar(articleId);
    await openOptionsDropdown();
    await click(".dropdown-item:contains('Lock Content')");
    await waitForOptionsDropdownClose();
    // lock icon should be shown in the topbar
    expect(".o_knowledge_header i.fa-lock").toHaveCount(1);
    await openOptionsDropdown();
    // The article is now Locked
    assertOptionsDropdown({ isInternalUser: true, canWrite: true, isLocked: true });
    await click(".dropdown-item:contains('Unlock')");
    await waitForOptionsDropdownClose();
    expect(".o_knowledge_header i.fa-lock").toHaveCount(0);
    await openOptionsDropdown();
    // hidden options should be shown again
    assertOptionsDropdown({ isInternalUser: true, canWrite: true });
});

test("Move Article", async () => {
    const mockServer = await makeMockServer();
    const articles = mockServer.env["knowledge.article"].create([
        { name: "a1" },
        { name: "a2" },
        { name: "a3" },
    ]);
    onRpc("get_valid_parent_options", ({ args: [id], kwargs: { search_term: searchTerm } }) => {
        expect(id).toBe(articles[0]);
        if (searchTerm) {
            expect(searchTerm).toBe("a2");
            asyncStep("get valid parent");
            return mockServer.env["knowledge.article"].browse([articles[1]]);
        }
        return mockServer.env["knowledge.article"].browse(articles.slice(1));
    });

    onRpc("move_to", ({ args: [id], kwargs: { parent_id: parentId } }) => {
        expect(id).toBe(articles[0]);
        expect(parentId).toBe(articles[1]);
        asyncStep("move");
        return true;
    });
    await mountTopbar(articles[0]);
    await openOptionsDropdown();
    await click(".dropdown-item:contains('Move To')");
    await waitFor(".o_knowledge_select_menu_dropdown");
    expect(".dropdown-item:contains('a1')").toHaveCount(0);
    expect(".dropdown-item:contains('a2')").toHaveCount(1);
    expect(".dropdown-item:contains('a3')").toHaveCount(1);
    await contains("input.dropdown-item").click();
    await contains("input.dropdown-item").edit("a2", { confirm: false });
    await runAllTimers();
    await waitForSteps(["get valid parent"]);
    expect(".dropdown-item:contains('a1')").toHaveCount(0);
    expect(".dropdown-item:contains('a2')").toHaveCount(1);
    expect(".dropdown-item:contains('a3')").toHaveCount(0);
    await click(".dropdown-item:contains('a2')");
    await click(waitFor(".modal-footer .btn-primary:interactive"));
    await waitForSteps(["move"]);
});

test("Open Version History", async () => {
    patchWithCleanup(OptionsDropdown.prototype, {
        async beforeOpen() {
            await super.beforeOpen();
            await this.props.record.load();
        },
    });
    const mockServer = await makeMockServer();
    const createDate = serializeDateTime(luxon.DateTime.now().minus({ minutes: 5 }));
    const articleId = mockServer.env["knowledge.article"].create({
        create_date: createDate,
    });
    await mountTopbar(articleId);
    await openOptionsDropdown();
    // button to open version history should not be shown as there is no history
    expect(".dropdown-item:contains('Open Version History')").toHaveCount(0);
    await click(".dropdown-toggle");
    await animationFrame();
    mockServer.env["knowledge.article"].write(articleId, {
        last_edition_date: serializeDateTime(luxon.DateTime.now()),
        html_field_history_metadata: { body: [{ revision_id: 5 }] },
    });
    await openOptionsDropdown();
    expect(".dropdown-item:contains('Open Version History')").toHaveCount(1);
});

test("Send Article to Trash", async () => {
    onRpc("knowledge.article", "action_redirect_to_parent", () => ({
        action: "redirect to parent",
    }));
    mockService("action", {
        doAction({ action }) {
            if (action === "redirect to parent") {
                asyncStep("redirect");
            }
        },
    });
    // redirect is mocked, record will be reloaded to test the topbar with the trashed article
    patchWithCleanup(OptionsDropdown.prototype, {
        async sendToTrash() {
            await super.sendToTrash();
            await this.props.record.load();
        },
    });
    const mockServer = await makeMockServer();
    const articleId = mockServer.env["knowledge.article"].create({});
    await mountTopbar(articleId);
    await openOptionsDropdown();
    await click(".dropdown-item:contains('Send to Trash')");
    await waitForOptionsDropdownClose();
    await waitForSteps(["redirect"]);
    // redirect was mocked, test topbar with trashed article
    await openOptionsDropdown();
    // options dropdown should only contain the restore button
    expect(".o_knowledge_options_dropdown .dropdown-item").toHaveCount(1);
    await click(".dropdown-item:contains('Restore from Trash')");
    await waitFor(".o-overlay-container:not(:has(.o_knowledge_options_dropdown))");
    await openOptionsDropdown();
    // options dropdown should be the default again
    assertOptionsDropdown({ isInternalUser: true, canWrite: true });
});

test.tags("desktop");
test("Toggle Properties Panel (desktop)", async () => {
    const mockServer = await makeMockServer();
    const parentId = mockServer.env["knowledge.article"].create({
        name: "parent",
        article_properties_definition: [{ name: "abc123", type: "char", string: "prop1" }],
    });
    mockServer.env["knowledge.article"].create([
        { name: "child1", parent_id: parentId, article_properties: [{ abc123: "a" }] },
        { name: "child2", parent_id: parentId, article_properties: [{}] },
    ]);
    localStorage.setItem("knowledge.unfolded.ids", parentId); // show children in sidebar
    await mountView({
        arch: /* xml */ `
            <form js_class="knowledge_article_view_form">
                <widget name="knowledge_topbar"/>
                <div class="row h-100 m-3">
                    <widget name="knowledge_properties_panel"/>
                </div>
            </form>
        `,
        resModel: "knowledge.article",
        resId: parentId,
        type: "form",
    });
    await waitFor(".o_knowledge_form_view");
    // properties panel and toggle button are not shown for root articles
    expect(".o_knowledge_header .btn-properties").toHaveCount(0);
    expect(".o_widget_knowledge_properties_panel").not.toBeVisible();
    expect(".o_field_properties").toHaveCount(0);
    // when opening an article with article properties, panel should be open
    await click(".o_article_name:contains('child1')");
    await waitFor(".o_article_active .o_article_name:contains('child1')");
    await animationFrame();
    expect(".o_widget_knowledge_properties_panel").toBeVisible();
    expect(".o_field_properties").toHaveCount(1);
    expect(".o_knowledge_header .btn-properties").toHaveClass("active");
    // close the properties panel
    await click(".o_knowledge_header .btn-properties");
    await animationFrame();
    expect(".o_widget_knowledge_properties_panel").not.toBeVisible();
    expect(".o_field_properties").toHaveCount(0);
    expect(".o_knowledge_header .btn-properties").not.toHaveClass("active");
    // reopen the properties panel
    await click(".o_knowledge_header .btn-properties");
    await animationFrame();
    expect(".o_widget_knowledge_properties_panel").toBeVisible();
    expect(".o_property_field").toHaveCount(1);
    expect(".o_knowledge_header .btn-properties").toHaveClass("active");
    // when opening an article whose parent has properties definitions, panel should remain open
    await click(".o_article_name:contains('child2')");
    await waitFor(".o_article_active .o_article_name:contains('child2')");
    await animationFrame();
    expect(".o_widget_knowledge_properties_panel").toBeVisible();
    expect(".o_field_properties").toHaveCount(1);
    expect(".o_knowledge_header .btn-properties").toHaveClass("active");
    // remove parent's properties definition
    mockServer.env["knowledge.article"].write(parentId, {
        article_properties_definition: [],
    });
    // when opening a child whose parent doesn't have properties definitions, panel should close
    await click(".o_article_name:contains('child1')");
    await waitFor(".o_article_active .o_article_name:contains('child1')");
    await animationFrame();
    expect(".o_widget_knowledge_properties_panel").not.toBeVisible();
    expect(".o_field_properties").toHaveCount(0);
    expect(".o_knowledge_header .btn-properties").toHaveCount(0);
});

test.tags("mobile");
test("Toggle Properties Panel (Mobile)", async () => {
    const mockServer = await makeMockServer();
    const parentId = mockServer.env["knowledge.article"].create({
        name: "parent",
        article_properties_definition: [{ name: "abc123", type: "char", string: "prop1" }],
    });
    mockServer.env["knowledge.article"].create([
        { name: "child1", parent_id: parentId, article_properties: [{ abc123: "a" }] },
        { name: "child2", parent_id: parentId, article_properties: [{}] },
    ]);
    localStorage.setItem("knowledge.unfolded.ids", parentId); // show children in sidebar
    patchWithCleanup(knowledgeTopbar, {
        fieldDependencies: [
            ...knowledgeTopbar.fieldDependencies.map((dependency) => ({
                ...dependency,
                readonly: false,
            })),
            { name: "create_date", type: "datetime" },
            { name: "last_edition_date", type: "datetime" },
            { name: "html_field_history_metadata", type: "jsonb" },
        ],
    });

    await mountView({
        arch: /* xml */ `
            <form js_class="knowledge_article_view_form">
                <widget name="knowledge_topbar"/>
                <div class="row h-100 m-3">
                    <widget name="knowledge_properties_panel"/>
                </div>
            </form>
        `,
        resModel: "knowledge.article",
        resId: parentId,
        type: "form",
    });
    await waitFor(".o_knowledge_form_view");
    // open an article with properties should not open the panel on mobile
    await click(".o_article_name:contains('child1')");
    await waitFor(".o_article_active .o_article_name:contains('child1')");
    await animationFrame();
    expect(".o_widget_knowledge_properties_panel").not.toBeVisible();
    expect(".o_field_properties").toHaveCount(0);
    // open the properties panel
    await openOptionsDropdown();
    expect(".dropdown-item:contains('Add Properties')").toHaveCount(0);
    expect(".dropdown-item:contains('Show Properties')").toHaveCount(1);
    expect(".dropdown-item:contains('Hide Properties')").toHaveCount(0);
    await click(".dropdown-item:contains('Show Properties')");
    await animationFrame();
    expect(".o_widget_knowledge_properties_panel").toBeVisible();
    expect(".o_field_properties").toHaveCount(1);
    await openOptionsDropdown();
    expect(".dropdown-item:contains('Add Properties')").toHaveCount(0);
    expect(".dropdown-item:contains('Show Properties')").toHaveCount(0);
    expect(".dropdown-item:contains('Hide Properties')").toHaveCount(1);
    // panel should remain open when opening an article with properties while the panel is opened
    await click(".o_article_name:contains('child2')");
    await waitFor(".o_article_active .o_article_name:contains('child2')");
    await animationFrame();
    expect(".o_widget_knowledge_properties_panel").toBeVisible();
    expect(".o_field_properties").toHaveCount(1);
    expect(".o_knowledge_header .btn-properties").toHaveClass("active");
    // remove parent's properties definition
    mockServer.env["knowledge.article"].write(parentId, {
        article_properties_definition: [],
    });
    // panel should close when opening an article without properties while the panel is opened
    await click(".o_article_name:contains('child1')");
    await waitFor(".o_article_active .o_article_name:contains('child1')");
    await animationFrame();
    expect(".o_widget_knowledge_properties_panel").not.toBeVisible();
    expect(".o_field_properties").toHaveCount(0);
});
