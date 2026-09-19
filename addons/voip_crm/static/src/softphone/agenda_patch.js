import { Agenda } from "@voip/softphone/agenda";

import { LeadButton } from "@voip_crm/lead_button";

import { patch } from "@web/core/utils/patch";

patch(Agenda.prototype, {
    get shouldShowLeadButton() {
        return this.voip.softphone.shouldShowLeadButton;
    },
    async onClickLead(activity) {
        const action = await this.orm.call("res.partner", "get_view_opportunities_action", [
            activity.partner?.id,
            activity.phone,
        ]);
        action.target = this.ui.isSmall ? "new" : "current";
        this.action.doAction(action);
    },
});

Agenda.components = { ...Agenda.components, LeadButton };
