import { isMobileOS } from "@web/core/browser/feature_detection";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
import { PromoteStudioDialog } from "@web_enterprise/webclient/promote_studio/promote_studio_dialog";
import { _t } from "@web/core/l10n/translation";

export const patchListRendererDesktop = () => ({
    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        const list = this.props.list;

        const { actionId, actionType, actionXmlId } = this.env.config || {};
        const resModel = this.props.list.resModel;

        // Start by determining if the current ListRenderer is in a context that would
        // allow the edition of the arch by studio.
        // It needs to be a full list view, in an action
        // (not a X2Many list, and not an "embedded" list in another component)
        // Also, there is not enough information when an action is in target new,
        // and this use case is fairly outside of the feature's scope
        const isPotentiallyEditable =
            !isMobileOS() &&
            !this.env.inDialog &&
            user.isSystem &&
            list === list.model.root &&
            actionId &&
            actionType === "ir.actions.act_window";

        const computeStudioEditable = () => {
            // Finalize the computation when the actionService is ready.
            // The following code is copied from studioService.
            if (!actionXmlId) {
                return false;
            }
            if (
                resModel.indexOf("settings") > -1 &&
                resModel.indexOf("x_") !== 0
            ) {
                return false; // settings views aren't editable; but x_settings is
            }
            if (resModel === "board.board") {
                return false; // dashboard isn't editable
            }
            if (resModel === "knowledge.article") {
                // The knowledge form view is very specific and custom, it doesn't make sense
                // to edit it. Editing the list and kanban is more debatable, but for simplicity's sake
                // we set them to not editable too.
                return false;
            }
            if (resModel === "account.bank.statement.line") {
                return false; // bank reconciliation isn't editable
            }
            return Boolean(resModel);
        };

        this.studioEditable = isPotentiallyEditable && computeStudioEditable();
    },

    isStudioEditable() {
        return this.studioEditable;
    },

    get displayOptionalFields() {
        return this.isStudioEditable() || super.displayOptionalFields;
    },

    /**
     * This function opens promote studio dialog
     *
     * @private
     */
    onSelectedAddCustomField() {
        this.env.services.dialog.add(PromoteStudioDialog, {
            title: _t("Odoo Studio - Add new fields to any view"),
        });
    },
});

export const unpatchListRendererDesktop = patch(ListRenderer.prototype, patchListRendererDesktop());
