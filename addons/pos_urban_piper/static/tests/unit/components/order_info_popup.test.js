import { test, expect } from "@odoo/hoot";
import { getUrbanPiperFilledOrder } from "@pos_urban_piper/../tests/unit/utils";
import { orderInfoPopup } from "@pos_urban_piper/point_of_sale_overrirde/app/components/popups/order_info_popup/order_info_popup";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { setupPosEnvForPrepDisplay } from "@pos_enterprise/../tests/unit/utils";

definePosModels();

test("getOrderDetails", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const order = await getUrbanPiperFilledOrder(store);
    order.delivery_status = "dispatched";

    const comp = await mountWithCleanup(orderInfoPopup, {
        props: { order, order_status: { dispatched: "Dispatched" }, close: () => {} },
    });
    expect(await comp.getOrderDetails()).toEqual({
        channelOtp: "TST-1756819673",
        fulfilmentMode: "partner",
        outletName: "Main Branch",
        paymentMode: "card",
        orderOtp: "123456",
    });
});
