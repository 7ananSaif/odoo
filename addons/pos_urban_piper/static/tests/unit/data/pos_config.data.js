import { patch } from "@web/core/utils/patch";
import { PosConfig } from "@point_of_sale/../tests/unit/data/pos_config.data";

patch(PosConfig.prototype, {
    get_delivery_data() {
        return {
            delivery_order_count: 1,
            delivery_providers: [{ code: "doordash", name: "DoorDash", id: 1 }],
            total_new_order: 2,
        };
    },
    get_urban_piper_provider_states() {
        return { doordash: true };
    },
    set_urban_piper_provider_states(config_id, newState) {
        return JSON.parse(newState);
    },
    order_status_update() {
        return { is_success: true, message: "test message" };
    },
    update_store_status(status) {},
});

PosConfig._records = PosConfig._records.map((record) => ({
    ...record,
    module_pos_urban_piper: true,
    urbanpiper_store_identifier: "test_urban_piper_store_identifier",
    urbanpiper_delivery_provider_ids: [1],
}));
