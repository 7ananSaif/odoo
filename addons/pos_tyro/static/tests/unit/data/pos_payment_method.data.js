import { patch } from "@web/core/utils/patch";
import { PosPaymentMethod } from "@point_of_sale/../tests/unit/data/pos_payment_method.data";

patch(PosPaymentMethod.prototype, {
    _load_pos_data_fields() {
        return [
            ...super._load_pos_data_fields(),
            "tyro_mode",
            "tyro_merchant_id",
            "tyro_terminal_id",
            "tyro_integration_key",
            "tyro_integrated_receipts",
            "tyro_always_print_merchant_receipt",
            "tyro_surcharge_product_id",
        ];
    },
});
