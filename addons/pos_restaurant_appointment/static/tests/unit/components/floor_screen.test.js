import { test, expect, describe } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { FloorScreen } from "@pos_restaurant/app/screens/floor_screen/floor_screen";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

definePosModels();

describe("pos_restaurant_appointment floor_screen.js", () => {
    test("floor_screen.js", async () => {
        const store = await setupPosEnv();
        const fs = await mountWithCleanup(FloorScreen);

        expect(fs.getFirstAppointment(store.models["restaurant.table"].get(2))).toEqual(
            store.models["calendar.event"].get(1)
        );

        expect(fs.getFirstAppointment(store.models["restaurant.table"].get(3))).toBe(false);

        expect(fs.isCustomerLate(store.models["restaurant.table"].get(2))).toBe(true);
        expect(fs.isCustomerLate(store.models["restaurant.table"].get(3))).toBe(false);
    });
});
