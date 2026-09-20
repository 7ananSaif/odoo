import { registry } from "@web/core/registry"


export async function AccountReturnCloseWizard(env, action) {
    const params = action.params || {};
    env.services.action.doAction({
        type: 'ir.actions.act_window_close'
    });
    return params.next_action;
}

registry.category("actions").add("action_return_close_wizard", AccountReturnCloseWizard)
