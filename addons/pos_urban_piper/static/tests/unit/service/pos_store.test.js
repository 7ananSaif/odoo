import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { test, expect } from "@odoo/hoot";
import { getUrbanPiperFilledOrder } from "@pos_urban_piper/../tests/unit/utils";
import { setupPosEnvForPrepDisplay } from "@pos_enterprise/../tests/unit/utils";

definePosModels();

test("getOrderData & getProviderState", async () => {
    const store = await setupPosEnvForPrepDisplay();
    expect(store.enabledProviders).toEqual({ doordash: true });
    expect(store.delivery_order_count).toEqual(1);
    expect(store.total_new_order).toEqual(2);
    expect(store.getOrderData(await getUrbanPiperFilledOrder(store), false)).toEqual({
        reprint: false,
        pos_reference: "1001",
        config_name: "Hoot",
        time: "10:30",
        tracking_number: "1001",
        preset_time: false,
        preset_name: "In",
        employee_name: "Administrator",
        internal_note: "",
        general_customer_note: "",
        changes: { title: "", data: [] },
        delivery_provider_id: { id: 1, name: "DoorDash" },
        order_otp: "TST-1756819673",
        prep_time: 25.0,
    });
    expect(await store.getProviderState()).toEqual({ doordash: true });
});
