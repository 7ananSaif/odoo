import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { test, expect } from "@odoo/hoot";
import { getUrbanPiperFilledOrder } from "@pos_urban_piper/../tests/unit/utils";
import { setupPosEnvForPrepDisplay } from "@pos_enterprise/../tests/unit/utils";

definePosModels();

test("isFutureOrder", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const order = await getUrbanPiperFilledOrder(store);
    order.delivery_datetime = "2025-03-01 06:02:25";
    expect(order.deliveryTime).toEqual("01/03/2025 06:02:25");
    expect(order.isFutureOrder()).toEqual(true);
});
