import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { expect, test } from "@odoo/hoot";
import { advanceTime } from "@odoo/hoot-dom";
import {
    contains,
    defineModels,
    fields,
    makeMockServer,
    models,
    mountView,
    onRpc,
} from "@web/../tests/web_test_helpers";

class KnowledgeArticle extends models.ServerModel {
    _name = "knowledge.article";

    category = fields.Generic({ default: "private" });

    get_sidebar_articles() {
        return {
            articles: this._filter(),
            favorite_ids: [],
        };
    }
}

defineMailModels();
defineModels([KnowledgeArticle]);

test("Search for an article", async () => {
    const mockServer = await makeMockServer();
    const articleId = mockServer.env["knowledge.article"].create({ name: "À la mâison" });
    onRpc("get_user_sorted_articles", () => [
        {
            id: articleId,
            icon: "",
            name: "À la mâison",
            is_user_favorite: false,
            root_article_id: [articleId, "À la mâison"],
        },
    ]);
    onRpc("has_access", () => true);
    await mountView({
        arch: /* xml */ `
            <form js_class="knowledge_article_view_form"/>
        `,
        resModel: "knowledge.article",
        resId: articleId,
        type: "form",
    });
    await contains(".o_knowledge_search").click();
    expect(".modal .o_command_palette").toHaveCount(1);
    expect(".o_command_palette .o_command").toHaveCount(1);
    expect(".o_command_palette .o_command_name").toHaveInnerHTML("À la mâison");
    await contains(".o_command_palette_search input").edit("a", { confirm: false });
    await advanceTime(500);
    expect(".o_command_palette .o_command_name").toHaveInnerHTML(
        '<span class="fw-bolder text-primary"> À </span> l <span class="fw-bolder text-primary"> a </span> m <span class="fw-bolder text-primary"> â </span> ison'
    );
});
