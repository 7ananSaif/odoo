import { describe, test, expect } from "@odoo/hoot";
import { definePosPrepDisplayModels } from "@pos_enterprise/../tests/unit/data/generate_model_definitions";
import {
    setupPosPrepDisplayEnv,
    createPrepDisplayTicket,
} from "@pos_enterprise/../tests/unit/utils";

const { DateTime } = luxon;

definePosPrepDisplayModels();

test("toggleTime", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    expect(store.selectedTimeIds.size).toBe(0);
    store.toggleTime("tomorrow");
    expect(store.selectedTimeIds.has("tomorrow")).toBe(true);
});

test("togglePreset", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    expect(store.selectedPresetIds.size).toBe(0);
    store.togglePreset(1);
    expect(store.selectedPresetIds.has(1)).toBe(true);
});

describe("checkStateVisibility", () => {
    describe("no filters", () => {
        test("returns true for state todo=true", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(true);
        });
        test("returns false for state with todo=false", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            state.todo = false;
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(true);
        });
    });

    describe("product category filter", () => {
        test("returns true for state with products in selected category", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            store.toggleCategory(state.categories[0]);
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(true);
        });

        test("returns false for state with no products in selected category", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            const otherCategory = store.data.models["pos.category"]
                .getAll()
                .find((c) => !state.categories.map((cat) => cat.id).includes(c.id));
            store.toggleCategory(otherCategory);
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(false);
        });
    });

    describe("product filter", () => {
        test("returns true for state with selected products", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            state.product.categoryIds = state.categories.map((c) => c.id);
            store.toggleProduct(state.product);
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(true);
        });

        test("returns false for state with no selected products", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            const otherProduct = store.data.models["product.product"]
                .getAll()
                .find((p) => p.id !== state.product.id);
            otherProduct.categoryIds = otherProduct.pos_categ_ids.map((c) => c.id);
            store.toggleProduct(otherProduct);
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(false);
        });
    });

    describe("time filter", () => {
        test("returns true for state in selected time", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            store.toggleTime("today");
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(true);
        });

        test("returns false for state not in selected time", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            store.toggleTime("yesterday");
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(false);
        });
        test("returns true when timeCheck is false but timeToShow is 0 and 'now' is selected", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            state.timeToShow = 0;
            store.toggleTime("now");
            store.toggleTime("tomorrow"); // force timeCheck to fail
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(true);
        });

        test("returns false when timeToShow is not 0 even if 'now' is selected", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            state.timeToShow = 10;
            store.toggleTime("now");
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(false);
        });
        test("returns true for order date two days in the future when 'next_days' is selected", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            state.prep_line_id.prep_order_id.pos_order_id.preset_time = DateTime.now().plus({
                days: 2,
            });
            store.toggleTime("next_days");
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(true);
        });

        test("returns false for tomorrow when only 'next_days' is selected", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            state.prep_line_id.prep_order_id.pos_order_id.preset_time = DateTime.now().plus({
                days: 1,
            });
            store.toggleTime("next_days");
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(false);
        });
        test("returns true when preset_time is missing and 'today' is selected", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            state.prep_line_id.prep_order_id.pos_order_id.preset_time = null;
            store.toggleTime("today");
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(true);
        });

        test("returns false when preset_time is missing and 'today' is not selected", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            state.prep_line_id.prep_order_id.pos_order_id.preset_time = null;
            store.toggleTime("tomorrow");
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(false);
        });
    });

    describe("preset filter", () => {
        test("returns true for state with selected preset", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            const preset = store.data.models["pos.preset"].getAll()[0];
            state.prep_line_id.prep_order_id.pos_order_id.preset_id = preset;
            store.togglePreset(preset.id);
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(true);
        });

        test("returns false for state with no selected preset", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            const preset = store.data.models["pos.preset"].getAll()[0];
            state.prep_line_id.prep_order_id.pos_order_id.preset_id = preset;
            const otherPreset = store.data.models["pos.preset"]
                .getAll()
                .find((p) => p.id !== preset.id);
            store.togglePreset(otherPreset.id);
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(false);
        });

        test("returns false when a preset is selected but state has no preset_id", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const state = store.data.models["pos.prep.state"].getAll()[0];
            const preset = store.data.models["pos.preset"].getAll()[0];
            store.togglePreset(preset.id);
            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(false);
        });
    });

    describe("combined filters", () => {
        test("returns false when one of multiple active filters does not match", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);

            const state = store.data.models["pos.prep.state"].getAll()[0];

            // Matching category
            store.toggleCategory(state.categories[0]);

            // Non-matching product
            const otherProduct = store.data.models["product.product"]
                .getAll()
                .find((p) => p.id !== state.product.id);
            otherProduct.categoryIds = otherProduct.pos_categ_ids.map((c) => c.id);
            store.toggleProduct(otherProduct);

            const visible = store.checkStateVisibility(state);
            expect(visible).toBe(false);
        });
    });
});

describe("orderNextStage", () => {
    test("returns next stage for given stage id", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createPrepDisplayTicket(store);
        const stages = store.data.models["pos.prep.stage"].getAll();
        const nextStage = store.orderNextStage(stages[0].id);
        expect(nextStage.id).toBe(stages[1].id);
    });

    test("returns first stage if current is last", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createPrepDisplayTicket(store);
        const lastStage = store.lastStage;
        const firstStage = store.orderNextStage(lastStage.id);
        expect(firstStage.id).toBe(store.data.models["pos.prep.stage"].getAll()[0].id);
    });
});

test("doneOrders", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const states = store.data.models["pos.prep.state"].getAll();
    await store.doneOrders(states);
    expect(states.every((s) => s.todo === false)).toBe(true);
});

test("changeStateStage", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const states = store.data.models["pos.prep.state"].getAll();
    await store.changeStateStage(states);
    await store.data.initData();
    expect(states[0].stage_id.id).toBe(2);
});

test("filteredOrders", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const states = store.data.models["pos.prep.state"].getAll();
    expect(store.filteredOrders.length).toBe(1);
    await store.changeStateStage(states);
    await store.data.initData();
    expect(store.filteredOrders.length).toBe(0);
});
