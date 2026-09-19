import { dragAndDropArticle, endKnowledgeTour, unfoldArticleFromSidebar } from './knowledge_tour_utils.js';
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add('knowledge_properties_tour', {
    url: '/odoo',
    steps: () => [stepUtils.showAppsMenuItem(), {
    // open Knowledge App
    trigger: '.o_app[data-menu-xmlid="knowledge.knowledge_menu_root"]',
    run: "click",
},
unfoldArticleFromSidebar("ParentArticle"),
{ // go to ChildArticle
    trigger: '.o_article .o_article_name:contains("ChildArticle")',
    run: 'click',
}, { // wait ChildArticle loading
    trigger: '.o_hierarchy_article_name input:value("ChildArticle")',
}, { // click on add properties button in dropdown
    trigger: '.o_knowledge_header .dropdown-toggle',
    run: 'click',
}, {
    trigger: '.dropdown-item:contains("Add Properties")',
    run: 'click',
}, {
    trigger: '.o_field_property_add button',
    run: 'click'
}, { // modify property name
    trigger: '.o_field_property_definition_header',
    run: "edit myproperty && click body",
},
{
    trigger: '.o_field_property_label:contains("myproperty")',
},
{ // verify property and finish property edition
    trigger: '.o_knowledge_editor .odoo-editor-editable',
    run: 'click',
}, { // go to InheritPropertiesArticle
    trigger: '.o_article .o_article_name:contains("InheritPropertiesArticle")',
    run: 'click',
}, { // wait InheritPropertiesArticle loading and move InheritPropertiesArticle under ParentArticle
    trigger: '.o_hierarchy_article_name input:value("InheritPropertiesArticle")',
    run: ({ queryOne }) => {
        dragAndDropArticle(
            queryOne('.o_article_handle:contains("InheritPropertiesArticle")'),
            queryOne('.o_article_handle:contains("ChildArticle")'),
        );
    },
}, { // verify property
    trigger: '.o_widget_knowledge_properties_panel .o_field_property_label:contains("myproperty")',
}, ...endKnowledgeTour()
]});
