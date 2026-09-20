import { useKnowledgeArticleSelector } from "@knowledge/hooks/knowledge_article_selector";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { uuid } from "@web/core/utils/strings";
import { useService } from "@web/core/utils/hooks";
import { AccountReportCogMenu } from "@account_reports/components/account_report/cog_menu/cog_menu";

patch(AccountReportCogMenu.prototype, {
    template: "accountant_knowledge.account_report_cog_menu",
    /** @override */
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.openArticleSelector = useKnowledgeArticleSelector();
        this.knowledgeCommandsService = useService("knowledgeCommandsService");
    },
    /** @override */
    get cogButtons() {
        const buttons = super.cogButtons;
        // Add a new button to insert the report in an article.
        buttons.push({
            name: _t("Insert in article"),
            /** @param {Event} event */
            onClick: (event) => {
                this.openArticleSelector(async (articleId) => {
                    const blueprint = document.createElement("div");
                    blueprint.setAttribute("data-oe-id", uuid());
                    blueprint.setAttribute("data-oe-protected", true);
                    blueprint.setAttribute("data-embedded", "accountReport");
                    blueprint.setAttribute(
                        "data-embedded-props",
                        JSON.stringify({
                            name: this.actionService.currentController.action.name,
                            options: this.env.controller.cachedFilterOptions,
                        })
                    );
                    this.knowledgeCommandsService.setPendingEmbeddedBlueprint({
                        embeddedBlueprint: blueprint,
                        model: "knowledge.article",
                        field: "body",
                        resId: articleId,
                    });
                    this.actionService.doAction("knowledge.ir_actions_server_knowledge_home_page", {
                        additionalContext: {
                            res_id: articleId,
                        },
                    });
                });
            },
        });
        return buttons;
    },
});
