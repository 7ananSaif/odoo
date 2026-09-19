import { _t } from "@web/core/l10n/translation";
import { useOwnedDialogs, useService } from "@web/core/utils/hooks";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

/**
 * @returns {function}
 */
export const useKnowledgeArticleSelector = () => {
    const openDialog = useOwnedDialogs();
    const orm = useService("orm");
    /** @param {function} onSelectCallback */
    return (onSelectCallback) => {
        openDialog(SelectCreateDialog, {
            title: _t("Select an article"),
            noCreate: false,
            multiSelect: false,
            resModel: "knowledge.article",
            context: {},
            domain: [
                ["user_has_write_access", "=", true],
                ["is_template", "=", false],
            ],
            onSelected: (resIds) => {
                onSelectCallback(resIds[0]);
            },
            onCreateEdit: async () => {
                const articleIds = await orm.call("knowledge.article", "article_create", [], {
                    is_private: true,
                });
                onSelectCallback(articleIds[0]);
            },
        });
    }
}
