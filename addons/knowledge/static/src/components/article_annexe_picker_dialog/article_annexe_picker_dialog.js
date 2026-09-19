import { ArticleTemplatePickerDialog } from "@knowledge/components/article_template_picker_dialog/article_template_picker_dialog";
import { ArticleAnnexePickerNoContentHelper } from "@knowledge/components/article_annexe_picker_dialog/article_annexe_picker_no_content_helper";

export class ArticleAnnexePickerDialog extends ArticleTemplatePickerDialog {
    static components = {
        ...ArticleTemplatePickerDialog.components,
        NoContentHelper: ArticleAnnexePickerNoContentHelper,
    };

    /**
     * @param {Object} template
     * @returns {boolean}
     */
    canDeleteTemplate(template) {
        return false;
    }
}
