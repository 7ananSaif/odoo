import { useService } from "@web/core/utils/hooks";

export function signFromActivity() {
    const orm = useService("orm");
    const actionService = useService("action");

    const openSignableDocument = {
        async openSignRequestAction(res_id) {
            const action = await orm.call("sign.request", "go_to_signable_document", [[res_id]]);
            if (action) {
                actionService.doAction(action);
                return true;
            }
            return false;
        }
    }
    return openSignableDocument;
}
