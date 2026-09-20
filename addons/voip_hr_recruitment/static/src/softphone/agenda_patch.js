import { Agenda } from "@voip/softphone/agenda";

import { ApplicantButton } from "@voip_hr_recruitment/applicant_button";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(Agenda.prototype, {
    onClickApplicant(contact) {
        const action = {
            type: "ir.actions.act_window",
            name: _t("Applicants"),
            res_model: "hr.applicant",
            target: this.ui.isSmall ? "new" : "current",
        };
        if (contact.applicant_ids.length === 1) {
            action.res_id = contact.applicant_ids[0].id;
            action.views = [[false, "form"]];
        } else {
            action.domain = [["partner_id", "=", contact.id]];
            action.views = [[false, "list"]];
        }
        this.action.doAction(action);
    },
});

Agenda.components = { ...Agenda.components, ApplicantButton };
