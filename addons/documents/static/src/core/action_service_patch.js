import { actionService } from "@web/webclient/actions/action_service";
import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";

/**
 * Saves the documents current view mode (only kanban or list)
 * in local storage to keep track of the user preferred mode.
 * Not applied in mobile environments (uses the "mobile_view_mode"
 * action field which defaults on "kanban").
 */
patch(actionService, {
    start(env) {
        const superReturn = super.start(env);
        const superSwitchView = superReturn.switchView;

        superReturn.switchView = async (viewType, props = {}, { newWindow } = {}) => {
            if (!env.isSmall && superReturn.currentController?.action?.xml_id == "documents.document_action") {
                const defaultViewType = browser.localStorage.getItem("documentsDefaultViewType");
                if (["kanban", "list"].includes(viewType) && defaultViewType != viewType) {
                    browser.localStorage.setItem("documentsDefaultViewType", viewType);
                }
            }
            return superSwitchView(viewType, props, newWindow);
        };
        return superReturn;
    },
});
