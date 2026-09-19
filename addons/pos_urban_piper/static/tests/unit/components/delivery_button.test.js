import { test, expect } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { DeliveryButton } from "@pos_urban_piper/point_of_sale_overrirde/app/delivery_button/delivery_button";
import { setupPosEnvForPrepDisplay } from "@pos_enterprise/../tests/unit/utils";

definePosModels();

test("handleToggle", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const comp = await mountWithCleanup(DeliveryButton, {});
    store.saveProviderState({ doordash: false });
    expect(store.enabledProviders["doordash"]).toBe(true);
    comp.handleToggle("doordash");
    expect(store.enabledProviders["doordash"]).toBe(false);
});
