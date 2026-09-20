import { Softphone } from "@voip/softphone/softphone_model";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";

patch(Softphone.prototype, {
    shouldShowLeadButton: false,

    setup() {
        super.setup();
        this.updateLeadButtonPermissions();
    },

    async updateLeadButtonPermissions() {
        this.shouldShowLeadButton =
            (await user.hasGroup("sales_team.group_sale_salesman")) ||
            (await user.hasGroup("sales_team.group_sale_manager"));
    },
});
