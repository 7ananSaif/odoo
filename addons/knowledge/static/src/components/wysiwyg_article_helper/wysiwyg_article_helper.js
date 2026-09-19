import { Component, onWillStart } from "@odoo/owl";
import { parseHTML } from "@html_editor/utils/html";
import { ArticleTemplatePickerDialog } from "@knowledge/components/article_template_picker_dialog/article_template_picker_dialog";
import { ItemCalendarPropsDialog } from "@knowledge/components/item_calendar_props_dialog/item_calendar_props_dialog";
import { PromptEmbeddedViewNameDialog } from "@knowledge/components/prompt_embedded_view_name_dialog/prompt_embedded_view_name_dialog";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { renderToFragment } from "@web/core/utils/render";
import { useService } from "@web/core/utils/hooks";
import { HtmlUpgradeManager } from "@html_editor/html_migrations/html_upgrade_manager";

export class WysiwygArticleHelper extends Component {
    static template = "knowledge.WysiwygArticleHelper";
    static props = {
        editor: { type: Object },
        isVisible: { type: Boolean },
        record: { type: Object },
    };

    setup() {
        this.actionService = useService("action");
        this.dialogService = useService("dialog");
        this.orm = useService("orm");
        onWillStart(async () => {
            this.isPortalUser = await user.hasGroup("base.group_portal");
        });
    }

    /** @param {string} body */
    replaceCurrentArticleBodyWith(body) {
        let newBody = new HtmlUpgradeManager().processForUpgrade(body);
        newBody = parseHTML(this.props.editor.document, body);
        newBody = this.props.editor.shared.sanitize.sanitize(newBody);
        this.props.editor.editable.replaceChildren(newBody);
        this.props.editor.shared.selection.setCursorEnd(this.props.editor.editable);
        this.props.editor.shared.history.addStep();
    }

    async onLoadTemplateBtnClick() {
        const { articles, templates } = await this.orm.call(
            "knowledge.article",
            "get_available_templates"
        );
        this.dialogService.add(ArticleTemplatePickerDialog, {
            articles: articles,
            templates: templates,
            /** @param {integer} articleId */
            onLoadArticle: async (articleId) => {
                const body = await this.orm.call(
                    "knowledge.article",
                    "apply_article_as_template",
                    [this.props.record.resId],
                    {
                        article_id: articleId
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
            /** @param {integer} templateId */
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
                // TODO: apply_template could return all modified values on the current
                // article and record.update would reload related components
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
            /** @param {integer} articleId */
            onDeleteArticle: async (articleId) => {
                if (this.props.record.resId === articleId) {
                    await this.props.record.save();
                }
                await this.orm.write("knowledge.article", [articleId], {
                    is_listed_in_templates_gallery: false,
                });
                if (this.props.record.resId === articleId) {
                    this.props.record.load();
                }
            },
            /** @param {integer} templateId */
            onDeleteTemplate: async (templateId) => {
                await this.orm.unlink("knowledge.article", [templateId]);
            },
        });
    }

    onBuildItemCalendarBtnClick() {
        this.dialogService.add(ItemCalendarPropsDialog, {
            isNew: true,
            knowledgeArticleId: this.props.record.resId,
            saveItemCalendarProps: async (name, itemCalendarProps) => {
                const title = name || _t("Article Items");
                const displayName = name
                    ? _t("Calendar of %s", name)
                    : _t("Calendar of Article Items");
                const embeddedProps = {
                    viewProps: {
                        additionalViewProps: { itemCalendarProps },
                        actionXmlId: "knowledge.knowledge_article_action_item_calendar",
                        displayName: displayName,
                        viewType: "calendar",
                        context: {
                            active_id: this.props.record.resId,
                            default_parent_id: this.props.record.resId,
                            default_is_article_item: true,
                        },
                    },
                };
                const fragment = renderToFragment("knowledge.ArticleItemTemplate", {
                    embeddedProps: JSON.stringify(embeddedProps),
                });
                this.props.editor.editable.replaceChildren(...fragment.children);
                this.props.editor.shared.selection.setCursorEnd(this.props.editor.editable);
                this.props.editor.shared.history.addStep();
                this.props.record.update({ name: title });
            },
        });
    }

    onBuildItemKanbanBtnClick() {
        this.dialogService.add(PromptEmbeddedViewNameDialog, {
            isNew: true,
            viewType: "kanban",
            /**
             * @param {string} name
             */
            save: async (name) => {
                const embeddedProps = {
                    viewProps: {
                        actionXmlId: "knowledge.knowledge_article_item_action_stages",
                        displayName: name
                            ? _t("Kanban of %s", name)
                            : _t("Kanban of Article Items"),
                        viewType: "kanban",
                        context: {
                            active_id: this.props.record.resId,
                            default_parent_id: this.props.record.resId,
                            default_is_article_item: true,
                        },
                    },
                };
                const title = name || _t("Article Items");
                await this.orm.call("knowledge.article", "create_default_item_stages", [
                    this.props.record.resId,
                ]);
                const fragment = renderToFragment("knowledge.ArticleItemTemplate", {
                    embeddedProps: JSON.stringify(embeddedProps),
                });
                this.props.editor.editable.replaceChildren(...fragment.children);
                this.props.editor.shared.selection.setCursorEnd(this.props.editor.editable);
                this.props.editor.shared.history.addStep();
                this.props.record.update({ name: title });
            },
        });
    }

    onBuildItemListBtnClick() {
        this.dialogService.add(PromptEmbeddedViewNameDialog, {
            isNew: true,
            viewType: "list",
            /**
             * @param {string} name
             */
            save: async (name) => {
                const embeddedProps = {
                    viewProps: {
                        actionXmlId: "knowledge.knowledge_article_item_action",
                        displayName: name ? _t("List of %s", name) : _t("List of Article Items"),
                        viewType: "list",
                        context: {
                            active_id: this.props.record.resId,
                            default_parent_id: this.props.record.resId,
                            default_is_article_item: true,
                        },
                    },
                };
                const title = name || _t("Article Items");

                const fragment = renderToFragment("knowledge.ArticleItemTemplate", {
                    embeddedProps: JSON.stringify(embeddedProps),
                });
                this.props.editor.editable.replaceChildren(...fragment.children);
                this.props.editor.shared.selection.setCursorEnd(this.props.editor.editable);
                this.props.editor.shared.history.addStep();
                this.props.record.update({ name: title });
            },
        });
    }
}
