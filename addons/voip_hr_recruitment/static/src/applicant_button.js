import { ResPartner } from "@mail/core/common/res_partner_model";

import { Component } from "@odoo/owl";

import { ActionButton } from "@voip/softphone/action_button";

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class ApplicantButton extends Component {
    static components = { ActionButton };
    static props = { contact: ResPartner };
    static template = "voip_hr_recruitment.ApplicantButton";

    setup() {
        this.action = useService("action");
        this.ui = useService("ui");
    }

    /** @param {ev} MouseEvent */
    onClickApplicant(ev) {
        const action = {
            type: "ir.actions.act_window",
            name: _t("Applicants"),
            res_model: "hr.applicant",
            target: this.ui.isSmall ? "new" : "current",
        };
        if (this.props.contact.applicant_ids.length === 1) {
            action.res_id = this.props.contact.applicant_ids[0].id;
            action.views = [[false, "form"]];
        } else {
            action.domain = [["partner_id", "=", this.props.contact.id]];
            action.views = [[false, "list"]];
        }
        this.action.doAction(action);
    }
}
