import { test, expect } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { ProductInfoPopup } from "@point_of_sale/app/components/popups/product_info_popup/product_info_popup";
import { setupPosEnvForPrepDisplay } from "@pos_enterprise/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

definePosModels();

test("switchFoodDeliveryAvailability and availableForFoodDelivery", async () => {
    const store = await setupPosEnvForPrepDisplay();
    store.addNewOrder();
    const product = store.models["product.template"].get(5);
    const info = await store.getProductInfo(product, 1);
    const comp = await mountWithCleanup(ProductInfoPopup, {
        props: {
            productTemplate: product,
            info,
            close: () => {},
        },
    });

    expect(Boolean(comp.showFoodDeliveryAvailability)).toBe(true);
    expect(comp.availableForFoodDelivery).toBe(true);

    comp.switchFoodDeliveryAvailability();
    // Mocking bus channel call
    store.notifyFoodDeliveryStatus({ product_ids: [5], status: false });

    expect(comp.availableForFoodDelivery).toBe(false);
});
