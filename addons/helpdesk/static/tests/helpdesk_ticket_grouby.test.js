import { describe, test, expect } from "@odoo/hoot";

import {
    quickCreateKanbanColumn,
    toggleKanbanColumnActions,
    mountView,
    onRpc,
} from "@web/../tests/web_test_helpers";

import { defineHelpdeskModels } from "@helpdesk/../tests/helpdesk_test_helpers";
import { HelpdeskTeam } from "@helpdesk/../tests/mock_server/mock_models/helpdesk_team";

describe.current.tags("desktop");
defineHelpdeskModels();

const kanbanViewArch = `
   <kanban default_group_by="stage_id" js_class="helpdesk_ticket_kanban">
        <templates>
            <t t-name="card">
                <field name="name"/>
                <field name="sla_deadline"/>
            </t>
        </templates>
    </kanban>
`;

test("Test group label for empty SLA Deadline in kanban", async () => {
    await mountView({
        resModel: "helpdesk.ticket",
        type: "kanban",
        groupBy: ["sla_deadline"],
        arch: kanbanViewArch,
    });
    expect(".o_column_title").toHaveCount(1);
});

test("Cannot create group if we are not in tickets of specific helpdesk team", async () => {
    await mountView({
        resModel: "helpdesk.ticket",
        type: "kanban",
        arch: kanbanViewArch,
    });
    expect(".o_kanban_group").toHaveCount(2);
    expect(".o_column_quick_create").toHaveCount(0);
});

test("Can create group if we are a specific helpdesk team", async () => {
    await mountView({
        resModel: "helpdesk.ticket",
        type: "kanban",
        arch: kanbanViewArch,
        context: {
            active_model: "helpdesk.team",
            default_team_id: 1,
            active_id: 1,
        },
    });
    expect(".o_kanban_group").toHaveCount(2);
    expect(".o_column_quick_create").toHaveCount(1);
    await quickCreateKanbanColumn();
    expect(".o_column_quick_create input").toHaveCount(1, {
        message: "the input should be visible",
    });
});

test("Delete a column in grouped on m2o", async (assert) => {
    await mountView({
        resModel: "helpdesk.ticket",
        type: "kanban",
        arch: kanbanViewArch,
    });
    onRpc("helpdesk.stage", "action_unlink_wizard", ({ method }) => {
        expect.step(method);
        return {
            type: "ir.actions.client",
            tag: "reload",
        };
    });

    const clickColumnAction = await toggleKanbanColumnActions(1);
    await clickColumnAction("Delete");
    expect.verifySteps(["action_unlink_wizard"]);
});

test("Prevent helpdesk users from reordering ticket stages", async () => {
    onRpc("has_group", ({ args }) => args[0][1] === "helpdesk.group_helpdesk_user");
    await mountView({
        resModel: "helpdesk.ticket",
        type: "kanban",
        groupBy: ["stage_id"],
        arch: kanbanViewArch,
    });
    expect(".o_group_draggable").toHaveCount(0);
});

test("Access for helpdesk manager to reordering ticket stages", async () => {
    await mountView({
        resModel: "helpdesk.ticket",
        type: "kanban",
        groupBy: ["stage_id"],
        arch: kanbanViewArch,
    });
    expect(".o_group_draggable").toHaveCount(2);
});

test("Verify stages nocontent helper is visible when all task stages are deleted in Task Kanban view", async () => {
    const newTeam = {
        id: 3,
        name: "Team 3",
    };
    HelpdeskTeam._records.push(newTeam);

    await mountView({
        resModel: "helpdesk.ticket",
        type: "kanban",
        arch: kanbanViewArch,
        context: {
            active_model: "helpdesk.stage.delete.wizard", // simulate stage deletion wizard
            default_team_id: newTeam.id,
        },
        domain: [["team_id", "=", newTeam.id]],
    });

    // Assertions to check for ghost column visibility
    expect(".o_kanban_header").toHaveCount(1, {
        message: "should have 1 column",
    });
    expect(".o_column_quick_create").toHaveCount(1);
    expect(".o_kanban_stages_nocontent").toHaveCount(1);
});
