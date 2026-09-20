import { PermissionPanel } from "@knowledge/components/permission_panel/permission_panel";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import {
    asyncStep,
    defineModels,
    MockServer,
    models,
    mountWithCleanup,
    patchWithCleanup,
    waitForSteps,
} from "@web/../tests/web_test_helpers";
import { user } from "@web/core/user";
import { getOrigin } from "@web/core/utils/urls";

import { beforeEach, expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";

class KnowledgeArticle extends models.ServerModel {
    get_permission_panel_members() {
        return [];
    }
}

defineMailModels();
defineModels([KnowledgeArticle]);

// remove "close" prop of popover
patchWithCleanup(PermissionPanel, {
    props: { reactiveRecordWrapper: Object },
});

async function mountPermissionPanel(articleId) {
    let data = KnowledgeArticle._records.find((record) => record.id === articleId);
    const reactiveRecordWrapper = {
        record: {
            load: () => {
                data = KnowledgeArticle._records.find((record) => record.id === articleId);
            },
            data,
            update: () => {
                data["website_published"] = !data["website_published"];
                asyncStep("toggle publish");
                pp.render();
            },
        },
    };
    await mountWithCleanup(PermissionPanel, { props: { reactiveRecordWrapper } });
    await animationFrame();
}

let pp;
const articleUrl = `${getOrigin()}/knowledge/article/1`;
beforeEach(() => {
    patchWithCleanup(PermissionPanel.prototype, {
        setup() {
            super.setup();
            pp = this;
        },
    });
    patchWithCleanup(navigator.clipboard, {
        writeText(value) {
            expect(value).toBe(articleUrl);
            asyncStep("copy to clipboard");
        },
    });
});

test("Publish an article", async () => {
    KnowledgeArticle._records = [{ id: 1, user_can_write: true, article_url: articleUrl }];
    await mountPermissionPanel(1);
    await animationFrame();
    expect("div:contains('Share to web') + .form-switch input").not.toBeChecked();
    await click(".o_knowledge_permission_panel .fa-globe");
    await animationFrame();
    waitForSteps(["toggle publish"]);
    expect("div:contains('Article shared to web') + .form-switch input").toBeChecked();
    await click(".o_clipboard_button");
    await waitForSteps(["copy to clipboard"]);
    await click("div:contains('Article shared to web') + .form-switch input");
    await animationFrame();
    await waitForSteps(["toggle publish"]);
    expect("div:contains('Share to web') + .form-switch input").not.toBeChecked();
    expect(".o_clipboard_button").toHaveCount(0);
});

test("Published readonly article", async () => {
    KnowledgeArticle._records = [{ id: 1, article_url: articleUrl }];
    patchWithCleanup(user, { isAdmin: false });
    await mountPermissionPanel(1);
    await animationFrame();
    // toggle should not be shown as user can't publish the article
    expect(".form-switch").toHaveCount(0);
    // clicking on the publish section shouldn't do anything as user can't publish it
    await click(".o_knowledge_permission_panel .fa-globe");
    await animationFrame();
    expect(".knowledge_published_status_message").toHaveText("Article not Published");
    // publish the article
    MockServer.env["knowledge.article"].write(1, { is_published: true });
    pp.load();
    await animationFrame();
    expect(".o_knowledge_permission_panel > div .fw-bold").toHaveText("Article shared to web");
    await click(".o_clipboard_button");
    await waitForSteps(["copy to clipboard"]);
});
