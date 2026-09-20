import { endKnowledgeTour } from './knowledge_tour_utils.js';
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

/**
 * Tests the cover picker feature when unsplash credentials are set. In this
 * case, the "Add Cover" button should either add a random picture from a
 * selected unsplash collection if no name is set on the article, either
 * add a random image using the article name as query word.
 */

function makeVisible(el) {
    if (el) {
        el.style.setProperty("visibility", "visible", "important");
        el.style.setProperty("opacity", "1", "important");
        el.style.setProperty("display", "block", "important");
    }
}

registry.category("web_tour.tours").add('knowledge_random_cover_tour', {
    url: '/odoo',
    steps: () => [stepUtils.showAppsMenuItem(), {
    // Open Knowledge App
    trigger: '.o_app[data-menu-xmlid="knowledge.knowledge_menu_root"]',
    run: "click",
}, {
    // Click on the "New Article" action
    trigger: '.o_knowledge_create_article',
    run: "click",
}, {
    // Make the add cover button visible (only visible on hover)
    trigger: '.o_article_active:contains("Untitled")',
    run: () => makeVisible(document.querySelector('.o_knowledge_add_cover')),
}, {
    // Click on add cover button
    trigger: '.o_knowledge_add_cover',
    run: "click",
}, {
    // Check that a cover has been added, and make the change cover button visible
    trigger: '.o_knowledge_cover .o_knowledge_cover_image',
    run: () => makeVisible(document.querySelector('.o_knowledge_replace_cover')),
}, {
    // Click on change cover button
    trigger: '.o_knowledge_replace_cover',
    run: "click",
},
{
    trigger: ".modal-body .o_load_done_msg",
},
{
    // Check that the cover selector has been opened, that no unsplash images can be
    // loaded as the article has no name and close the cover selector
    trigger: '.modal-footer .btn-secondary',
    run: "click",
}, {
    // Make the remove cover button visible
    trigger: '.o_knowledge_edit_cover_buttons',
    run: () => makeVisible(document.querySelector('.o_knowledge_remove_cover')),
}, {
    // Remove the cover of the article
    trigger: '.o_knowledge_remove_cover',
    run: "click",
}, {
    // Set the name of the article
    trigger: '.o_hierarchy_article_name > input',
    run: "edit Birds && click body",
}, {
    // Make the add cover button visible
    trigger: '.o_article_active:contains("Birds")',
    run: () => makeVisible(document.querySelector('.o_knowledge_add_cover')),
}, {
    // Click on add cover button
    trigger: '.o_knowledge_add_cover',
    run: "click",
}, {
    // Check that a cover has been added and make the change cover button visible
    trigger: '.o_knowledge_cover .o_knowledge_cover_image',
    run: () => makeVisible(document.querySelector('.o_knowledge_replace_cover')),
}, {
    // Click on change cover button
    trigger: '.o_knowledge_replace_cover',
    run: "click",
},
{
    trigger: ".modal-body .o_load_more",
},
{
    // Check that the cover selector has been opened, that other unsplash
    // images can be loaded and close the cover selector
    trigger: '.modal-footer .btn-secondary',
    run: "click",
}, ...endKnowledgeTour()
]});
