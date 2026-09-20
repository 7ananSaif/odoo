import { test, expect } from "@odoo/hoot";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

definePosModels();

test("canEditPayment", async () => {
    const store = await setupPosEnv();
    const company = store.config.company_id;
    store.addNewOrder();
    const order = store.getOrder();
    expect(store.canEditPayment(order)).toBe(false);
    company.l10n_at_is_fon_authenticated = false;
    expect(store.canEditPayment(order)).toBe(true);
});
