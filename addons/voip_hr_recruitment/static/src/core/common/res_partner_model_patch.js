import { ResPartner } from "@mail/core/common/res_partner_model";

// ensure voip patch is applied first
import "@voip/core/common/res_partner_model_patch";

import { patch } from "@web/core/utils/patch";

patch(ResPartner.prototype, {
    /**
     * @override
     * @returns {string}
     */
    get voipName() {
        return (
            this.applicant_ids.find((applicant) => applicant.partner_name)?.partner_name ||
            super.voipName
        );
    },
});
