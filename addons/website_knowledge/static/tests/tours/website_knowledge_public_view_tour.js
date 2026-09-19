import { registry } from "@web/core/registry";

function checkSearchArticles(expectedArticles) {
    if (document.querySelectorAll(".o_article_search_item").length !== expectedArticles.length) {
        console.error("Incorrect number of articles returned by search");
    }
    for (const articleName of expectedArticles) {
        if (!this.queryOne(`.o_article_search_item:contains(${articleName})`)) {
            console.error(`Missing article "${articleName}" in search results`);
        }
    }
}

registry.category("web_tour.tours").add("website_knowledge_public_view_tour", {
    steps: () => [
        {
            content: "Check that the article has the right display name",
            trigger: ".o_knowledge_header span:contains('🐣 Published Root')",
        },
        {
            content: "Check that the cover has been loaded",
            trigger: ".o_knowledge_cover img",
        },
        {
            content: "Check the article icon",
            trigger: ".o_knowledge_icon:contains('🐣')",
        },
        {
            content: "Check the article content",
            trigger: ".o_knowledge_article .o_readonly h1:contains('Published Root')",
        },
        {
            content: "Check that the sidebar initially only has the subsite root article",
            trigger: ".o_knowledge_sidebar .o_article:contains('Published Root')",
            run: () => {
                if (document.querySelectorAll(".o_knowledge_sidebar .o_article").length > 1) {
                    console.error("Sidebar has more articles than expected");
                }
            },
        },
        {
            content: "Unfold the article in the sidebar",
            trigger: ".o_knowledge_sidebar .o_article .o_article_icon",
            run: "click",
        },
        {
            content: "Check that only the published child articles is shown",
            trigger: ".o_knowledge_sidebar .o_article ul .o_article .o_article_name:contains('Published Child')",
            run: () => {
                if (
                    document.querySelectorAll(".o_knowledge_sidebar .o_article ul .o_article")
                        .length > 1
                ) {
                    console.error("Sidebar has more articles than expected");
                }
            },
        },
        {
            content: "Open the article from the sidebar",
            trigger: ".o_knowledge_sidebar .o_article ul .o_article .o_article_name",
            run: "click",
        },
        {
            content: "Check that the article was opened",
            trigger: ".o_knowledge_header span:contains('📄 Published Child')",
        },
        {
            content: "Check that active article in the sidebar was updated",
            trigger: ".o_knowledge_sidebar .o_article_active .o_article_name:contains(Published Child)",
        },
        {
            content: "Click on search bar",
            trigger: ".o_knowledge_sidebar button:has(i.fa-search)",
            run: "click",
        },
        {
            content: "Search for the word 'publi'",
            trigger: ".o_article_search_dialog input",
            run: "edit publi",
        },
        {
            content: "Check that search only returns the published articles",
            trigger: ".o_article_search_item",
            run: (helpers) =>
                checkSearchArticles.call(helpers, [
                    "Published Subchild",
                    "Published Child",
                    "Published Root",
                    "Published Item",
                ]),
        },
        {
            content: "Search for the word 'content'",
            trigger: ".o_article_search_dialog input",
            run: "edit content",
        },
        {
            content: "Check that the search only returns the published child containing 'content'",
            trigger: ".o_article_search_dialog:not(:contains('Published Root'))",
            run: (helpers) => checkSearchArticles.call(helpers, ["Untitled"]),
        },
        {
            content: "Click on the article to open it",
            trigger: ".o_article_search_item",
            run: "click",
        },
        {
            content: "Check that the untitled article was opened",
            trigger: ".o_knowledge_header:contains('📄 Untitled')",
        },
        {
            content: "Check that article is visible in the sidebar",
            trigger: ".o_knowledge_sidebar .o_article_active .o_article_name:contains('Untitled')",
        },
    ],
});
