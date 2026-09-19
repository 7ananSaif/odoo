import { describe, test, expect } from "@odoo/hoot";
import { definePosPrepDisplayModels } from "@pos_enterprise/../tests/unit/data/generate_model_definitions";
import {
    setupPosPrepDisplayEnv,
    createPrepDisplayTicket,
    createComboPrepDisplayTicket,
} from "@pos_enterprise/../tests/unit/utils";
import { Order } from "@pos_enterprise/app/components/order/order";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";

definePosPrepDisplayModels();

describe("changeOrderlineStatus", () => {
    test("should toggle todo state for single orderline", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createPrepDisplayTicket(store);
        const orders = store.filteredOrders;
        const comp = await mountWithCleanup(Order, { props: { order: orders[0] } });
        const line = comp.orderlines[0];
        const initial = line.todo;
        await comp.changeOrderlineStatus(line);
        expect(line.todo).toBe(!initial);
    });

    test("should mark parent done when all combo children are done", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createComboPrepDisplayTicket(store);
        const orders = store.filteredOrders;
        const comp = await mountWithCleanup(Order, { props: { order: orders[0] } });
        await comp.changeOrderlineStatus(comp.orderlines[1]);
        await comp.changeOrderlineStatus(comp.orderlines[2]);
        expect(comp.orderlines[0].todo).toBe(false);
    });

    test("should mark all combo children done when parent is done", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createComboPrepDisplayTicket(store);
        const orders = store.filteredOrders;
        const comp = await mountWithCleanup(Order, { props: { order: orders[0] } });
        const parent = comp.orderlines[0];
        const initial = parent.todo;
        await comp.changeOrderlineStatus(parent);
        expect(comp.orderlines.map((l) => l.todo)).toEqual(comp.orderlines.map(() => !initial));
    });
});

test("should mark order as done", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const orders = store.filteredOrders;
    const comp = await mountWithCleanup(Order, { props: { order: orders[0] } });
    await comp.doneOrder();
    expect(comp.props.order.states.length).toBeGreaterThan(0);
});

describe("orderlines", () => {
    test("should return correct orderlines count", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createPrepDisplayTicket(store);
        const orders = store.filteredOrders;
        const comp = await mountWithCleanup(Order, { props: { order: orders[0] } });
        expect(comp.orderlines.length).toBe(2);
    });

    test("should return all lines for combo order", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createComboPrepDisplayTicket(store);
        const orders = store.filteredOrders;
        const comp = await mountWithCleanup(Order, { props: { order: orders[0] } });
        expect(comp.orderlines.length).toBe(3);
    });
});

test("pdisNotes", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store, {
        extraOrderFields: {
            internal_note: '[{"text":"Wait","colorIndex":3}]',
        },
    });
    const orders = store.filteredOrders;
    const comp = await mountWithCleanup(Order, { props: { order: orders[0] } });
    expect(comp.pdisNotes).toEqual([{ text: "Wait", colorIndex: 3 }]);
});
