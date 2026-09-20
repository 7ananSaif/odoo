import { ProductTemplate } from "@point_of_sale/app/models/product_template";
import { patch } from "@web/core/utils/patch";

patch(ProductTemplate.prototype, {
    isAvailableForFoodDelivery(configId) {
        return this.raw.urbanpiper_pos_config_ids.includes(configId);
    },
    setFoodDeliveryAvailability(status, configId) {
        let availableConfigIds = [...this.raw.urbanpiper_pos_config_ids, configId];
        if (!status) {
            availableConfigIds = availableConfigIds.filter((id) => id !== configId);
        }
        this.update({
            urbanpiper_pos_config_ids: availableConfigIds,
        });
    },
});
