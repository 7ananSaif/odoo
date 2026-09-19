import { patch } from "@web/core/utils/patch";
import { ArticleAnnexePickerDialog } from "@knowledge/components/article_annexe_picker_dialog/article_annexe_picker_dialog";
import { WysiwygArticleHelper } from "@knowledge/components/wysiwyg_article_helper/wysiwyg_article_helper";

patch(WysiwygArticleHelper.prototype, {
    /** @override */
    async onLoadTemplateBtnClick() {
        if (!this.props.record.data.inherited_audit_report_id?.records.length) {
            return await super.onLoadTemplateBtnClick();
        }
        const templates = await this.orm.call(
            "knowledge.article",
            "get_suggested_templates",
            [[this.props.record.data.parent_id.id]]
        );
        this.dialogService.add(ArticleAnnexePickerDialog, {
            articles: [],
            templates: templates,
            previewRenderingContext: {
                target_article_id: this.props.record.id
            },
            onLoadArticle: () => {},
            /** @param {integer} articleId */
            onLoadTemplate: async (templateId) => {
                const body = await this.orm.call(
                    "knowledge.article",
                    "apply_template",
                    [this.props.record.resId],
                    {
                        template_id: templateId,
                        skip_body_update: true,
                    }
                );
                this.replaceCurrentArticleBodyWith(body);
                await this.actionService.doAction(
                    "knowledge.ir_actions_server_knowledge_home_page",
                    {
                        stackPosition: "replaceCurrentAction",
                        additionalContext: {
                            res_id: this.props.record.resId,
                        },
                    }
                );
            },
            onDeleteArticle: () => {},
            /** @param {integer} templateId */
            onDeleteTemplate: async (templateId) => {
                await this.orm.unlink("knowledge.article", [templateId]);
            },
        });
    },
});
