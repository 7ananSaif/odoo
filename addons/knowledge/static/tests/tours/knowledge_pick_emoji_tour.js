import { endKnowledgeTour } from '@knowledge/../tests/tours/knowledge_tour_utils';
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add('knowledge_pick_emoji_tour', {
    url: '/odoo',
    steps: () => [stepUtils.showAppsMenuItem(), {
    // open Knowledge App
    trigger: '.o_app[data-menu-xmlid="knowledge.knowledge_menu_root"]',
    run: "click",
}, {
    // click on the "New Article" action
    trigger: '.o_knowledge_create_article',
    run: "click",
}, {
    trigger: 'section[data-section="private"] .o_article .o_article_name:contains("Untitled")',
 // check that the article is correctly created (private section)
}, {
    trigger: '.o_knowledge_header .dropdown-toggle',
    run: "click",
}, {
    // add a random emoji
    trigger: '.dropdown-item:contains("Add Icon")',
    run: 'click',
}, {
    trigger: '.o_knowledge_body .o_article_emoji',
    run: 'click',
}, {
    trigger: '.o-Emoji[data-codepoints="😃"]',
    run: 'click',
}, {
    // check that the emoji has been properly changed in the article body
    trigger: '.o_knowledge_body .o_article_emoji:contains(😃)',
}, {
    // check that the emoji has been properly changed in the header
    trigger: '.o_knowledge_header .o_article_emoji:contains(😃)',
}, {
    // check that the emoji has been properly changed in the aside block
    trigger: '.o_knowledge_sidebar .o_article_emoji:contains(😃)',
}, ...endKnowledgeTour()
]});
