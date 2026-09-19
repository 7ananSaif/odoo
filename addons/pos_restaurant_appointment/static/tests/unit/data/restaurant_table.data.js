import { patch } from "@web/core/utils/patch";
import { RestaurantTable } from "@pos_restaurant/../tests/unit/data/restaurant_table.data";

patch(RestaurantTable.prototype, {
    _load_pos_data_fields() {
        return [...super._load_pos_data_fields(), "appointment_resource_id"];
    },
});
