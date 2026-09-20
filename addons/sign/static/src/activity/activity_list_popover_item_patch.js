import { ActivityListPopoverItem } from "@mail/core/web/activity_list_popover_item";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { signFromActivity } from "./sign_from_activity_hook";

patch(ActivityListPopoverItem.prototype, {
    setup() {
        super.setup();
        this.user = user.userId;
        const functions = signFromActivity();
        Object.assign(this, functions);
    },

    get hasMarkDoneButton() {
        return super.hasMarkDoneButton && this.props.activity.activity_category !== "sign_request";
    },

    async onClickRequestSign() {
        const { res_model, res_id } = this.props.activity;
        if (res_model === 'sign.request') {
            // When activity is linked to sign request model we directly open the document for sign.
            const result = await this.openSignRequestAction(res_id);
            if (result) {
                return;
            }
        }
        // Skip 'sign.request' model as it's not allowed in the Reference field selection in the backend.
        const documentReference = (res_model && res_model !== 'sign.request') && res_id ? `${res_model},${res_id}` : false;
        await this.props.activity.requestSignature(this.props.onActivityChanged, documentReference, res_model, res_id);
    },
});
