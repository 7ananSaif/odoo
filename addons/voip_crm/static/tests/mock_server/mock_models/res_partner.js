import { ResPartner as MailResPartner } from "@voip/../tests/mock_server/mock_models/res_partner";

export class ResPartner extends MailResPartner {
    /** @override */
    _voip_get_store_fields() {
        return ["opportunity_count", ...super._voip_get_store_fields()];
    }
}
