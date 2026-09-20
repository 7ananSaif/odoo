import { expect, test, beforeEach, describe, getFixture } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { mockDate } from "@odoo/hoot-mock";
import { contains } from "@mail/../tests/mail_test_helpers";
import { onRpc, mountWithCleanup, getService, defineActions } from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";

import {
    definePlanningModels,
    planningModels,
    ResourceResource,
    PlanningRole,
    PlanningRecurrency,
} from "./planning_mock_models";

describe.current.tags("desktop");

class PlanningSlot extends planningModels.PlanningSlot {
    _views = {
        list: `<list js_class="planning_tree">
                    <field name="recurrency_id" column_invisible="True"/>
                </list>`,
    };
}

planningModels.PlanningSlot = PlanningSlot;

definePlanningModels();
defineActions([
    {
        id: 1,
        name: "planning action",
        res_model: "planning.slot",
        type: "ir.actions.act_window",
        views: [[false, "list"]],
    },
]);

let target;

beforeEach(() => {
    PlanningSlot._records = [
        {
            id: 1,
            name: "First Record",
            start_datetime: "2019-03-11 08:00:00",
            end_datetime: "2019-03-11 12:00:00",
            resource_id: 1,
            color: 7,
            role_id: 1,
            state: "draft",
            repeat: true,
            recurrency_id: 1,
        },
        {
            id: 2,
            name: "Second Record",
            start_datetime: "2019-03-13 08:00:00",
            end_datetime: "2019-03-13 12:00:00",
            resource_id: 2,
            color: 9,
            role_id: 2,
            state: "published",
        },
        {
            id: 3,
            name: "Third Record",
            start_datetime: "2019-03-13 08:00:00",
            end_datetime: "2019-03-13 12:00:00",
            resource_id: 2,
            color: 9,
            role_id: 2,
            state: "published",
        },
    ];
    (PlanningRecurrency._records = [{ id: 1, repeat_interval: 1 }]),
        (ResourceResource._records = [
            { id: 1, name: "Chaganlal" },
            { id: 2, name: "Maganlal" },
        ]);
    PlanningRole._records = [
        { id: 1, name: "JavaScript Developer", color: 1 },
        { id: 2, name: "Functional Consultant", color: 2 },
    ];

    onRpc("check_access_rights", () => {
        return true;
    });

    mockDate("2019-03-13 00:00:00", +1);
    target = getFixture();
});

test("Display modal to choose recurrence type when deleting recurrent task", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    await click("div input.form-check-input");

    await contains("button.btn.btn-secondary", { count: 3 });
    await click("button.btn.btn-secondary");

    await contains(".fa-trash-o");
    await click(".fa-trash-o");

    await contains("h4.modal-title");
    expect(target.querySelector("h4.modal-title")).toHaveText("Delete Recurring Shift");
});

test("Display confirm delete modal when deleting non recurrent task", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    const inputs = target.querySelectorAll("div input.form-check-input");
    await inputs[2].click();
    await inputs[3].click();

    await contains("button.btn.btn-secondary", { count: 3 });
    await click("button.btn.btn-secondary");

    await contains(".fa-trash-o");
    await click(".fa-trash-o");

    await contains("h4.modal-title");
    expect(target.querySelector("h4.modal-title")).toHaveText("Bye-bye, record!");
});
