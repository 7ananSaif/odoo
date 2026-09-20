import { test, expect } from "@odoo/hoot";
import { setupPosEnvForPrepDisplay } from "@pos_enterprise/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

definePosModels();

test("setFoodDeliveryAvailability and isAvailableForFoodDelivery", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const product = store.models["product.template"].get(5);
    expect(product.isAvailableForFoodDelivery(1)).toBe(true);

    product.setFoodDeliveryAvailability(false, 1);
    expect(product.isAvailableForFoodDelivery(1)).toBe(false);

    product.setFoodDeliveryAvailability(true, 1);
    expect(product.isAvailableForFoodDelivery(1)).toBe(true);
    // For different Config
    product.setFoodDeliveryAvailability(false, 2);
    expect(product.isAvailableForFoodDelivery(1)).toBe(true);
});
