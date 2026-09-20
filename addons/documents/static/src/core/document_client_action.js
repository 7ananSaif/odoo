import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";

/**
 * Restores the user preferred documents view mode ("kanban" or "list").
 * Not applied in mobile environments (uses the "mobile_view_mode"
 * action field which defaults on "kanban").
 */
async function documentActionPreference(env, action, options) {
    const viewType = browser.localStorage.getItem("documentsDefaultViewType");

    const nextAction = await env.services.action.loadAction("documents.document_action");

    return env.services.action.doAction(
        {
            ...nextAction,
            context: action.context,
            domain: action.domain,
        },
        { ...options, viewType }
    );
}

registry.category("actions").add("document_action_preference", documentActionPreference);
