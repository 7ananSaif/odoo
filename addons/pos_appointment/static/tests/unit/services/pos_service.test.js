import { test, expect, describe } from "@odoo/hoot";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { patchWithCleanup, onRpc } from "@web/../tests/web_test_helpers";

definePosModels();

describe("pos_store", () => {
    test("manageBookings", async () => {
        const store = await setupPosEnv();
        onRpc("calendar.event", "action_open_booking_gantt_view", () => ({
            type: "ir.actions.act_window",
            name: "Gantt View",
        }));
        let actionCalled = null;
        patchWithCleanup(store.action, {
            async doAction(action) {
                actionCalled = action;
            },
        });
        await store.manageBookings();
        expect(actionCalled).toEqual({
            type: "ir.actions.act_window",
            name: "Gantt View",
        });
    });

    test("editBooking", async () => {
        const store = await setupPosEnv();
        let actionCalled = null;
        patchWithCleanup(store.action, {
            async doAction(action) {
                actionCalled = action;
            },
        });
        onRpc("calendar.event", "action_open_booking_form_view", (rpcParams) => {
            expect(rpcParams.args).toEqual([42]);
            return {
                type: "ir.actions.act_window",
                name: "Edit Booking",
            };
        });
        await store.editBooking({ id: 42 });
        expect(actionCalled).toEqual({
            type: "ir.actions.act_window",
            name: "Edit Booking",
        });
    });
});
