import { describe, test, expect } from "@odoo/hoot";
import { definePosPrepDisplayModels } from "@pos_enterprise/../tests/unit/data/generate_model_definitions";
import {
    setupPosPrepDisplayEnv,
    createPrepDisplayTicket,
} from "@pos_enterprise/../tests/unit/utils";
import { PrepDisplay } from "@pos_enterprise/app/components/preparation_display/preparation_display";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";

definePosPrepDisplayModels();

test("filterSelected", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const comp = await mountWithCleanup(PrepDisplay, {});
    const category = store.data.models["pos.category"].getAll()[0];
    store.toggleCategory(category);
    expect(comp.filterSelected).toBe(1);
});

test("selectedStage returns correct stage", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const comp = await mountWithCleanup(PrepDisplay, {});
    const expectedStage = store.data.models["pos.prep.stage"].get(store.selectedStageId);
    expect(comp.selectedStage.id).toBe(expectedStage.id);
});

test("archiveAllVisibleOrders marks all last stage orders as done", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const comp = await mountWithCleanup(PrepDisplay, {});
    const states = store.data.models["pos.prep.state"].getAll();
    states.forEach((s) => (s.stage_id = store.lastStage));
    comp.archiveAllVisibleOrders();
    expect(states.every((s) => s.todo === false)).toBe(true);
});

test("clears selected filters and sets time to all", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const comp = await mountWithCleanup(PrepDisplay, {});
    store.selectedCategoryIds.add(1);
    store.selectedProductIds.add(2);
    store.selectedTimeIds.add("today");
    store.selectedPresetIds.add(1);
    comp.resetFilter();
    expect(store.selectedCategoryIds.size).toBe(0);
    expect(store.selectedProductIds.size).toBe(0);
    expect(store.selectedTimeIds.size).toBe(0);
    expect(store.selectedPresetIds.size).toBe(0);
});

test("toggles the showCategoryFilter flag", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const comp = await mountWithCleanup(PrepDisplay, {});
    const initial = store.showCategoryFilter;
    comp.toggleCategoryFilter();
    expect(store.showCategoryFilter).toBe(!initial);
});

describe("menu handling", () => {
    test("isBurgerMenuClosed returns true when menu is closed", async () => {
        await setupPosPrepDisplayEnv();
        const comp = await mountWithCleanup(PrepDisplay, {});
        comp.state.isMenuOpened = false;
        expect(comp.isBurgerMenuClosed()).toBe(true);
    });

    test("openMenu sets isMenuOpened to true", async () => {
        await setupPosPrepDisplayEnv();
        const comp = await mountWithCleanup(PrepDisplay, {});
        comp.openMenu();
        expect(comp.state.isMenuOpened).toBe(true);
    });

    test("closeMenu sets isMenuOpened to false", async () => {
        await setupPosPrepDisplayEnv();
        const comp = await mountWithCleanup(PrepDisplay, {});
        comp.state.isMenuOpened = true;
        comp.closeMenu();
        expect(comp.state.isMenuOpened).toBe(false);
    });
});
