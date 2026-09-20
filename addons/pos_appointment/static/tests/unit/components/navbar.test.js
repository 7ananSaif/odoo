import { expect, test } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

definePosModels();

test("mainButton", async () => {
    const store = await setupPosEnv();
    store.router.state = {
        current: "ActionScreen",
        params: {
            actionName: "manage-booking",
        },
    };
    const navbar = await mountWithCleanup(Navbar, store.env);
    expect(navbar.mainButton).toBe("booking");
});
