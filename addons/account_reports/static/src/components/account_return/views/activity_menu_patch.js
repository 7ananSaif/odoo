import { ActivityMenu } from "@mail/core/web/activity_menu";
import { patch } from "@web/core/utils/patch";


patch(ActivityMenu.prototype, {
    availableViews(group) {
        if (group.model !== "account.return") {
            return super.availableViews(...arguments);
        }
        return [[false, "kanban"]];
    },
});
