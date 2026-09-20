import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { animationFrame, click } from "@odoo/hoot-dom";

import { mockService, mountView } from "@web/../tests/web_test_helpers";

import { defineEsgModels, EsgCarbonEmissionReport, EsgEmissionFactor } from "./esg_models";

defineEsgModels();

describe.current.tags("desktop");
beforeEach(() => {
    EsgEmissionFactor._records = [{ id: 1, name: "bar" }];
    EsgCarbonEmissionReport._records = [
        {
            id: 1,
            name: "foo",
            quantity: 1,
            esg_emission_factor_id: 1,
            esg_emissions_value: 1,
        },
    ];
});

test("esg.carbon.emission.report (list): hide Add a line button", async () => {
    await mountView({
        resModel: "esg.carbon.emission.report",
        type: "list",
    });

    expect(".o_group_field_row_add").toHaveCount(0);
});

test("esg.carbon.emission.report (list): hide Add a line button even if the list is grouped", async () => {
    await mountView({
        resModel: "esg.carbon.emission.report",
        type: "list",
        groupBy: ["esg_emission_factor_id"],
    });

    expect(".o_group_field_row_add").toHaveCount(0);
    expect(".o_group_header").toHaveCount(1);
    expect(".o_group_header.o_group_open").toHaveCount(0);
    await click(".o_group_header");
    await animationFrame();
    expect(".o_group_header.o_group_open").toHaveCount(1);
    expect(".o_group_field_row_add").toHaveCount(0);
});

test("esg.carbon.emission.report (list): New button should open `esg.other.emission` form view", async () => {
    mockService("action", {
        doAction(params) {
            expect(params.type).toBe("ir.actions.act_window");
            expect(params.res_model).toBe("esg.other.emission");
            expect(params.target).toBe("current");
            expect.step(`doAction -> ${params.res_model}`);
        },
    });
    await mountView({
        resModel: "esg.carbon.emission.report",
        type: "list",
    });

    expect(".o_list_view .o_list_button_add").toHaveCount(1);
    await click(".o_list_button_add");
    await animationFrame();
    expect.verifySteps(["doAction -> esg.other.emission"]);
});
