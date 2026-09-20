import { patch } from "@web/core/utils/patch";
import { ProductTemplate } from "@point_of_sale/../tests/unit/data/product_template.data";

patch(ProductTemplate.prototype, {
    _load_pos_data_fields() {
        return [...super._load_pos_data_fields(), "urbanpiper_pos_config_ids"];
    },

    _load_pos_data_read(records) {
        records.forEach((product) => {
            product["_synced_on_urbanpiper"] = true;
        });
        return records;
    },

    toggle_product_food_delivery_availability(recordId, configId) {
        return {
            status: "success",
        };
    },
});

ProductTemplate._records = ProductTemplate._records.map((record) => {
    if (record.id == 5) {
        record.urbanpiper_pos_config_ids = [1];
    }
    return record;
});
