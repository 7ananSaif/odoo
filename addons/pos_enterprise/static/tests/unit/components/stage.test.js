import { test, expect } from "@odoo/hoot";
import { definePosPrepDisplayModels } from "@pos_enterprise/../tests/unit/data/generate_model_definitions";
import {
    setupPosPrepDisplayEnv,
    createPrepDisplayTicket,
} from "@pos_enterprise/../tests/unit/utils";
import { Stages } from "@pos_enterprise/app/components/stages/stages";
import { PrepDisplay } from "@pos_enterprise/app/components/preparation_display/preparation_display";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";

definePosPrepDisplayModels();

test("orderCount and preparation_display.archiveAllVisibleOrders", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const stages = store.data.models["pos.prep.stage"].getAll();
    const comp = await mountWithCleanup(Stages, { props: { stages } });
    expect(comp.orderCount(stages[0].id)).toBe(1);
    expect(comp.orderCount(stages[1].id)).toBe(0);
    const states = store.data.models["pos.prep.state"].getAll();
    await store.changeStateStage(states);
    await store.data.initData();
    expect(comp.orderCount(stages[0].id)).toBe(0);
    expect(comp.orderCount(stages[1].id)).toBe(1);

    const prepDisplayComp = await mountWithCleanup(PrepDisplay, {});
    await store.changeStateStage(states);
    await prepDisplayComp.archiveAllVisibleOrders();
    expect(comp.orderCount(stages[2].id)).toBe(0);
});
