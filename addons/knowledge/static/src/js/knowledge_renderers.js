import { FormRenderer } from "@web/views/form/form_renderer";
import { useExternalListener } from "@odoo/owl";

export class KnowledgeArticleFormRenderer extends FormRenderer {

    //--------------------------------------------------------------------------
    // Component
    //--------------------------------------------------------------------------
    setup() {
        super.setup();
        useExternalListener(document, "click", event => {
            if (event.target.classList.contains("o_nocontent_create_btn")) {
                this.env.createArticle("private");
            }
        });
    }
}
