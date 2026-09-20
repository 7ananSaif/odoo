import { formView } from '@web/views/form/form_view';
import { registry } from "@web/core/registry";
import { KnowledgeArticleFormController } from './knowledge_controller.js';
import { KnowledgeArticleFormRenderer } from './knowledge_renderers.js';

class KnowledgeModel extends formView.Model {
    static withCache = false;
}

export const knowledgeArticleFormView = {
    ...formView,
    Controller: KnowledgeArticleFormController,
    Model: KnowledgeModel,
    Renderer: KnowledgeArticleFormRenderer,
    display: {controlPanel: false}
};

registry.category('views').add('knowledge_article_view_form', knowledgeArticleFormView);
