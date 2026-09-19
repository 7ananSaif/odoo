import { expect, test } from "@odoo/hoot";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { getFilledOrder, setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { mountWithCleanup, onRpc, patchWithCleanup } from "@web/../tests/web_test_helpers";

definePosModels();

test("pos_iot_payment_six", async () => {
    onRpc("/hw_drivers/action", () => true);
    onRpc("/iot_drivers/event", () => true);
    patchWithCleanup(console, { log: () => {} });

    // Fonts
    onRpc("/css", () => "");
    onRpc("/fonts/*", () => "");
    onRpc("/web/static/*", () => "");

    const store = await setupPosEnv();
    const order = await getFilledOrder(store);
    const sixPm = store.models["pos.payment.method"].find(
        (pm) => pm.use_payment_terminal === "six_iot"
    );
    const pmScreen = await mountWithCleanup(PaymentScreen, {
        props: { orderUuid: order.uuid },
    });

    await pmScreen.addNewPaymentLine(sixPm);
    const pmLine = order.payment_ids.at(-1);
    expect(store.paymentTerminalInProgress).toBe(true);
    expect(sixPm.payment_terminal.terminal.iotId).toBe(2);

    const paymentData = sixPm.payment_terminal.getPaymentData(pmLine.uuid);
    expect(paymentData.amount).toBe(Math.round(pmLine.amount * 100));
    expect(paymentData.cid).toBe(pmLine.uuid);

    const line = sixPm.payment_terminal.getPaymentLineForMessage(order, {
        cid: pmLine.uuid,
        owner: store.env.services.iot_longpolling._session_id,
    });
    expect(!line).toBeEmpty();
    expect(line.amount).toBe(pmLine.amount);

    expect(pmLine.payment_status).toBe("waiting");
    await sixPm.payment_terminal._resolvePayment(true);
    expect(pmLine.payment_status).toBe("done");
});
