import { HtmlField } from "@html_editor/fields/html_field";
import { htmlEditorVersions } from "@html_editor/html_migrations/html_migrations_utils";
import { mockKnowledgeCommentsService } from "@knowledge/../tests/knowledge_test_helpers";
import { WithLazyLoading } from "@knowledge/components/with_lazy_loading/with_lazy_loading";
import { EmbeddedViewLinkComponent } from "@knowledge/editor/embedded_components/backend/embedded_view_link/embedded_view_link";
import { EmbeddedView } from "@knowledge/views/embedded_view";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { before, beforeEach, describe, expect, test } from "@odoo/hoot";
import { onMounted, toRaw } from "@odoo/owl";
import {
    defineModels,
    fields,
    models,
    patchWithCleanup,
    defineActions,
    getService,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { Deferred } from "@web/core/utils/concurrency";
import { SearchModel } from "@web/search/search_model";
import { WebClient } from "@web/webclient/webclient";

const VERSIONS = htmlEditorVersions();
const CURRENT_VERSION = VERSIONS.at(-1);

const searchModelState = JSON.stringify({
    nextGroupId: 2,
    nextGroupNumber: 2,
    nextId: 2,
    query: [{ searchItemId: 1 }],
    searchItems: {
        1: {
            description: "myFavorite",
            isDefault: true,
            domain: [["name", "ilike", "view"]],
            context: {},
            userId: 1,
            type: "favorite",
            id: 1,
            groupId: 1,
            groupNumber: 1,
            orderBy: [],
        },
    },
    searchPanelInfo: {
        className: "",
        viewTypes: ["list"],
        loaded: false,
        shouldReload: false,
    },
    sections: [],
});

const embeddedViewProps = {
    viewProps: {
        actionXmlId: "knowledge_article_action_test",
        context: {
            knowledge_search_model_state: searchModelState,
        },
        displayName: "Articles List",
        favoriteFilters: {
            customFavorite: {
                name: "customFavorite",
                is_default: false,
                model_id: "article",
                domain: [["name", "ilike", "view"]],
                context: {},
                user_id: 1,
            },
        },
        id: "embedid",
        viewType: "list",
    },
};

const embeddedViewLinkProps = {
    viewProps: {
        actionXmlId: "knowledge_article_action_test",
        context: {
            knowledge_search_model_state: searchModelState,
        },
        displayName: "Articles List",
        viewType: "list",
    },
};

class Article extends models.Model {
    body = fields.Html({ trim: true });
    name = fields.Char();
    sequence = fields.Integer();

    _records = [
        {
            id: 1,
            name: "view_2.0",
            body: `
                <div data-embedded="view" data-embedded-props='${JSON.stringify(
                    embeddedViewProps
                )}'></div>
                <p><br></p>`,
            sequence: 1,
        },
        {
            id: 2,
            name: "viewLink_2.0",
            body: `
                <p>
                    <span data-embedded="viewLink" data-embedded-props='${JSON.stringify(
                        embeddedViewLinkProps
                    )}'></span>
                </p>
            `,
            sequence: 2,
        },
    ];

    _views = {
        list: `
            <list default_order="sequence" string="Articles">
                <field name="sequence" widget="handle"/>
                <field name="name"/>
            </list>
        `,
        form: `
            <form js_class="knowledge_article_view_form">
                <sheet>
                    <div class="o_knowledge_editor">
                        <field name="body" widget="knowledge_html"/>
                    </div>
                </sheet>
            </form>
        `,
        search: `
            <search></search>
        `,
    };
}

defineMailModels();
defineModels([Article]);

onRpc("get_sidebar_articles", () => ({ articles: [], favorite_ids: [] }));

// Prevent instantiation of the color picker
onRpc("render_public_asset", () => false);

onRpc("has_access", () => true);

defineActions([
    {
        id: 1,
        xml_id: "knowledge_article_action_test",
        name: "articleTest",
        res_model: "article",
        type: "ir.actions.act_window",
        views: [
            [false, "form"],
            [false, "list"],
        ],
    },
]);

describe("test migration of embedded views and view links filters", () => {
    let htmlFieldComponent;
    beforeEach(() => {
        patchWithCleanup(HtmlField.prototype, {
            setup() {
                super.setup();
                htmlFieldComponent = this;
            },
        });
    });

    test("Ensure that embedded views filters and favorites have their `user_id` field converted to `user_ids`", async function () {
        const searchModelPromise = new Deferred();
        before(() => {
            mockKnowledgeCommentsService();
            patchWithCleanup(WithLazyLoading.prototype, {
                setup() {
                    super.setup();
                    onMounted(() => {
                        this.state.isLoaded = true;
                    });
                },
            });
            patchWithCleanup(EmbeddedView.prototype, {
                async loadView() {
                    await super.loadView(...arguments);
                    patchWithCleanup(this.withSearchProps.SearchModel.prototype, {
                        async load() {
                            await super.load(...arguments);
                            if (this.context.knowledgeEmbeddedViewId === "embedid") {
                                searchModelPromise.resolve(this);
                            }
                        },
                    });
                },
            });
        });
        await mountWithCleanup(WebClient);
        await getService("action").doAction("knowledge_article_action_test", {
            props: { resId: 1 },
            viewType: "form",
        });
        const searchModel = await searchModelPromise;
        expect(searchModel.query).toEqual([{ searchItemId: 1 }]);
        const myFavorite = searchModel.searchItems[1];
        expect(myFavorite.description).toEqual("myFavorite");
        expect(toRaw(myFavorite.userIds)).toEqual([]);
        expect(myFavorite.userId).toEqual(undefined);
        const customFavorite = searchModel.searchItems[2];
        expect(customFavorite.description).toEqual("customFavorite");
        expect(toRaw(customFavorite.userIds)).toEqual([]);
        expect(customFavorite.userId).toEqual(undefined);
        expect(
            htmlFieldComponent.editor
                .getElContent()
                .querySelector(`[data-oe-version="${CURRENT_VERSION}"]`)
        ).toHaveCount(1);
    });

    test("Ensure that embedded views links filters have their `user_id` field converted to `user_ids`", async function () {
        const viewLinkPromise = new Deferred();
        const searchModelPromise = new Deferred();
        let saveSearchModel = false;
        before(() => {
            mockKnowledgeCommentsService();
            patchWithCleanup(SearchModel.prototype, {
                async load() {
                    await super.load(...arguments);
                    if (saveSearchModel) {
                        searchModelPromise.resolve(this);
                    }
                },
                /**
                 * This method is voided for the test because it overwrites
                 * favorites with real favorite records data (which are not
                 * defined here).
                 * For the purpose of this test, only the data contained in the
                 * searchModel state should be tested (to ensure that the
                 * upgrade actually happened). In a real situation,
                 * _reconciliateFavorites will also "fix" some properties
                 * with the most up to date information from actual irFilters
                 * records, but that is done independently from the JS upgrade.
                 */
                _reconciliateFavorites() {},
            });
            patchWithCleanup(EmbeddedViewLinkComponent.prototype, {
                setup() {
                    super.setup();
                    onMounted(() => {
                        viewLinkPromise.resolve(this);
                    });
                },
            });
        });
        await mountWithCleanup(WebClient);
        await getService("action").doAction("knowledge_article_action_test", {
            props: { resId: 2 },
            viewType: "form",
        });
        const viewLink = await viewLinkPromise;
        expect(
            htmlFieldComponent.editor
                .getElContent()
                .querySelector(`[data-oe-version="${CURRENT_VERSION}"]`)
        ).toHaveCount(1);
        saveSearchModel = true;
        viewLink.openViewLink();
        const searchModel = await searchModelPromise;
        expect(searchModel.query).toEqual([{ searchItemId: 1 }]);
        const myFavorite = searchModel.searchItems[1];
        expect(myFavorite.description).toEqual("myFavorite");
        expect(toRaw(myFavorite.userIds)).toEqual([]);
        expect(myFavorite.userId).toEqual(undefined);
    });
});
