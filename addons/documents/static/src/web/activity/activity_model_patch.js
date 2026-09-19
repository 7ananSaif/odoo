import { Activity } from "@mail/core/common/activity_model";

import { patch } from "@web/core/utils/patch";

/** @type {import("models").Activity} */
const activityPatch = {
    async markAsDone(attachmentIds = []) {
        await super.markAsDone(...arguments);
        if (this.chaining_type === "trigger") {
            // Refresh as the trigger might have created a new document
            this?.store?.env?.services["document.document"]?.reload();
        }
    },
};
patch(Activity.prototype, activityPatch);
