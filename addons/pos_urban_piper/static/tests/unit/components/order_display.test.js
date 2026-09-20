import { test, expect } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { OrderDisplay } from "@point_of_sale/app/components/order_display/order_display";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { getUrbanPiperFilledOrder } from "@pos_urban_piper/../tests/unit/utils";
import { setupPosEnvForPrepDisplay } from "@pos_enterprise/../tests/unit/utils";
const { DateTime } = luxon;

definePosModels();

test("showTimer and _computeRemainingTime", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const order = await getUrbanPiperFilledOrder(store);
    const comp = await mountWithCleanup(OrderDisplay, {
        props: {
            orderAcceptTime: DateTime.now().ts,
            orderPrepTime: 15,
            order,
            slots: {},
        },
    });
    expect(comp.showTimer).toBe(true);
    expect(comp._computeRemainingTime()).toBe(15);

    order.state = "paid";
    const comp2 = await mountWithCleanup(OrderDisplay, {
        props: {
            orderAcceptTime: DateTime.now().ts,
            orderPrepTime: 15,
            order,
            slots: {},
        },
    });
    expect(comp2.showTimer).toBeEmpty();
    expect(comp2._computeRemainingTime()).toBeEmpty();
});
