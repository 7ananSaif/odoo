import { patch } from "@web/core/utils/patch";
import { ResPartner } from "@point_of_sale/../tests/unit/data/res_partner.data";

patch(ResPartner.prototype, {
    _load_pos_data_fields() {
        return [
            ...super._load_pos_data_fields(),
            "credit_limit",
            "total_due",
            "use_partner_credit_limit",
            "pos_orders_amount_due",
            "invoices_amount_due",
            "commercial_partner_id",
        ];
    },

    async get_all_total_due(partner_ids, config_id) {
        return partner_ids.map((id) => ({
            "res.partner": [
                {
                    id,
                    total_due: 0,
                    pos_orders_amount_due: 0,
                    invoices_amount_due: 0,
                },
            ],
        }));
    },

    async get_total_due(partner_id, config_id) {
        return {
            "res.partner": [
                {
                    id: partner_id,
                    total_due: 0,
                    pos_orders_amount_due: 0,
                    invoices_amount_due: 0,
                },
            ],
        };
    },
});
