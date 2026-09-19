import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { test, expect } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { getUrbanPiperFilledOrder } from "@pos_urban_piper/../tests/unit/utils";
import { setupPosEnvForPrepDisplay } from "@pos_enterprise/../tests/unit/utils";

definePosModels();

test("_getSearchFields", async () => {
    await setupPosEnvForPrepDisplay();
    const comp = await mountWithCleanup(TicketScreen, {});
    const fields = comp._getSearchFields();
    expect(Object.keys(fields)).toEqual([
        "REFERENCE",
        "RECEIPT_NUMBER",
        "INVOICE_NUMBER",
        "DATE",
        "PARTNER",
        "DELIVERYPROVIDER",
        "ORDERSTATUS",
    ]);
});

test("_acceptOrder, _dispatchOrder, _completeOrder", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const order = await getUrbanPiperFilledOrder(store);
    const comp = await mountWithCleanup(TicketScreen, {});

    await comp._acceptOrder(order);
    expect(comp.state.upState).toBeEmpty();
    expect(order.delivery_status).toBe("acknowledged");
    expect(order.uiState.orderAcceptTime).not.toBeEmpty();

    await comp._dispatchOrder(order);
    expect(order.delivery_status).toBe("dispatched");
    expect(comp.state.upState).toBeEmpty();

    await comp._completeOrder(order);
    expect(order.delivery_status).toBe("completed");
    expect(comp.state.upState).toBeEmpty();
});

test("getFilteredOrderList", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const comp = await mountWithCleanup(TicketScreen, {});
    (await getUrbanPiperFilledOrder(store)).delivery_status = "food_ready";
    (await getUrbanPiperFilledOrder(store)).delivery_status = "dispatched";
    (await getUrbanPiperFilledOrder(store)).delivery_status = "completed";
    (await getUrbanPiperFilledOrder(store)).delivery_status = "placed";
    comp.state.upState = "DONE";
    expect((await comp.getFilteredOrderList()).map((o) => o.delivery_status)).toEqual([
        "food_ready",
        "dispatched",
        "completed",
    ]);
});

test("getDate", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const order = await getUrbanPiperFilledOrder(store);
    const comp = await mountWithCleanup(TicketScreen, {});
    expect(comp.getDate(order)).toBe("Today");
    order.date_order = luxon.DateTime.now().minus({ days: 1 });
    expect(comp.getDate(order)).toMatch(/\d{2}\/\d{2}\/\d{4}/);
});

test("postRefund", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const order = await getUrbanPiperFilledOrder(store);
    const comp = await mountWithCleanup(TicketScreen, {});
    comp.postRefund(order);
    expect(order.isDeliveryRefundOrder).toBe(true);
});
