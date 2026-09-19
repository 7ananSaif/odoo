import { test, expect } from "@odoo/hoot";
import { getFilledOrder, setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

definePosModels();

test("createAmountPerPaymentTypeArray", async () => {
    const store = await setupPosEnv();
    const order = await getFilledOrder(store);
    const cashPaymentMethod = store.models["pos.payment.method"].get(1);
    order.addPaymentline(cashPaymentMethod);
    let result = order._createAmountPerPaymentTypeArray();
    expect(result).toEqual([{ payment_type: "CASH", amount: "17.85" }]);

    order.payment_ids[0].setAmount(10);
    order.addPaymentline(cashPaymentMethod);
    result = order._createAmountPerPaymentTypeArray();
    expect(result).toEqual([{ payment_type: "CASH", amount: "17.85" }]);

    order.removePaymentline(order.payment_ids[1]);
    result = order._createAmountPerPaymentTypeArray();
    expect(result).toEqual([
        { payment_type: "CASH", amount: "10.00" },
        { payment_type: "CASH", amount: "7.85" },
    ]);
});
