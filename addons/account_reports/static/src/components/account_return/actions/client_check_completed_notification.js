import { registry } from "@web/core/registry"


export async function AccountReturnRefreshHandler(env, action) {
    const params = action.params || {};
    env.bus.trigger("return_reload_model", {resIds: params.return_ids});
    return params.next_action;
}

registry.category("actions").add("action_return_refresh", AccountReturnRefreshHandler)
