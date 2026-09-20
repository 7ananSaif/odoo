import { SearchBarMenu } from "@web/search/search_bar_menu/search_bar_menu";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(SearchBarMenu.prototype, {
    setup() {
        super.setup();
        this.dialogService = useService("dialog");
    },
    onDeleteKnowledgeFavoriteItem(itemId) {
        const dialogProps = {
            title: _t("Warning"),
            body: _t("This filter is global and will be removed for everyone."),
            confirmLabel: _t("Delete Filter"),
            confirm: () => this.env.searchModel.deleteFavorite?.(itemId),
            cancel: () => {},
        };
        this.dialogService.add(ConfirmationDialog, dialogProps);
    },
});
