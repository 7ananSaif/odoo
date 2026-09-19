import { dragAndDropArticle } from "@knowledge/../tests/tours/knowledge_tour_utils";
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("knowledge_sidebar_readonly_tour", {
    url: "/odoo",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            // Open the Knowledge App
            trigger: '.o_app[data-menu-xmlid="knowledge.knowledge_menu_root"]',
            run: "click",
        },
        {
            trigger:
                '.o_knowledge_tree .o_article:contains("Workspace Article") + .o_article:contains("Private Article")',
        },
        {
            // Unfold the private article and check that articles are in the correct
            // order to make the move possible
            trigger: '.o_article.readonly .o_article_handle:contains("Private Article") .o_article_icon',
            run: 'hover && click .o_article.readonly .o_article_handle:contains("Private Article") .o_article_caret .fa-caret-right',
        },
        {
            // Check that article has been unfolded and move an article under a readonly article (fails)
            trigger: '.o_article:contains("Private Child")',
            run: ({ queryOne }) => {
                dragAndDropArticle(
                    queryOne(
                        'section[data-section="workspace"] .o_article_name:contains("Workspace Article")'
                    ),
                    queryOne(
                        'section[data-section="workspace"] .o_article_name:contains("Private Article")'
                    )
                );
            },
        },
        {
            trigger: '.modal-title:contains("Move cancelled")',
        },
        {
            // Close the move cancelled modal
            trigger: ".modal-footer .btn-primary",
            run: "click",
        },
        {
            // Move a readonly article (fails)
            trigger:
                '.o_knowledge_tree .o_article:contains("Workspace Article") + .o_article:contains("Private Article")',
            run: ({ queryOne }) => {
                dragAndDropArticle(
                    queryOne(
                        'section[data-section="workspace"] .o_article_name:contains("Private Article")'
                    ),
                    queryOne(
                        'section[data-section="workspace"] .o_article_name:contains("Workspace Article")'
                    )
                );
            },
        },
        {
            trigger:
                '.o_knowledge_tree .o_article:contains("Workspace Article") + .o_article:contains("Private Article")',
        },
        {
            // Check that article did not move and try to change icon of readable article (fails)
            trigger: '.o_article:contains("Private Article") .o_article_emoji:contains("📄")',
            run: "click",
        },
        {
            // Check that emoji picker did not show up
            trigger: "body:not(:has(.o-EmojiPicker))",
        },
    ],
});
