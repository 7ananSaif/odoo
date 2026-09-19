import { mailModels } from "@mail/../tests/mail_test_helpers";
import { hover } from "@odoo/hoot-dom";
import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";
import { TaskGanttRenderer } from "@project_enterprise/views/task_gantt/task_gantt_renderer";
import { findComponent, onRpc } from "@web/../tests/web_test_helpers";
import {
    getConnectorMap,
    getConnectorStroke,
} from "@web_gantt/../tests/gantt_dependency_helpers";
import { SELECTORS, mountGanttView } from "@web_gantt/../tests/web_gantt_test_helpers";
import { COLORS } from "@web_gantt/gantt_connector";

import { projectModels, defineProjectModels } from "@project/../tests/project_models";

describe.current.tags("desktop");

const ganttViewParams = {
    resModel: "project.task",
    arch: `
        <gantt
            js_class="task_gantt"
            date_start="planned_date_begin"
            date_stop="date_deadline"
            default_scale="month"
            dependency_field="depend_on_ids"
        />
    `,
    groupBy: ["user_ids"],
};

defineProjectModels();

beforeEach(() => {
    mailModels.ResUsers._records = [
        { id: 1, name: "User 1" },
        { id: 2, name: "User 2" },
        { id: 3, name: "User 3" },
        { id: 4, name: "User 4" },
        ...mailModels.ResUsers._records,
    ];
    projectModels.ProjectProject._records = [{ id: 1, name: "Project 1" }];
    projectModels.ProjectTask._records = [
        {
            id: 1,
            name: "Task 1",
            planned_date_begin: "2021-10-19 06:30:12",
            date_deadline: "2021-10-19 07:29:59",
            project_id: 1,
            user_ids: [2],
            depend_on_ids: [],
            display_warning_dependency_in_gantt: false,
        },
        {
            id: 2,
            name: "Task 2",
            planned_date_begin: "2021-10-18 06:30:12",
            date_deadline: "2021-10-18 07:29:59",
            project_id: 1,
            user_ids: [2],
            depend_on_ids: [1],
        },
        {
            id: 3,
            name: "Task 3",
            planned_date_begin: "2021-10-19 06:30:12",
            date_deadline: "2021-10-19 07:29:59",
            project_id: 1,
            user_ids: [2],
            depend_on_ids: [],
        },
        {
            id: 4,
            name: "Task 4",
            planned_date_begin: "2021-10-18 06:30:12",
            date_deadline: "2021-10-18 07:29:59",
            project_id: 1,
            user_ids: [2],
            depend_on_ids: [3],
            display_warning_dependency_in_gantt: false,
        },
        {
            id: 5,
            name: "Task 5",
            planned_date_begin: "2021-10-19 06:30:12",
            date_deadline: "2021-10-19 07:29:59",
            project_id: 1,
            user_ids: [2],
            depend_on_ids: [],
        },
        {
            id: 6,
            name: "Task 6",
            planned_date_begin: "2021-10-18 06:30:12",
            date_deadline: "2021-10-18 07:29:59",
            project_id: 1,
            user_ids: [2],
            depend_on_ids: [5],
        },
        {
            id: 7,
            name: "Task 7",
            planned_date_begin: "2021-10-18 06:30:12",
            date_deadline: "2021-10-19 07:29:59",
            project_id: 1,
            user_ids: [2],
            depend_on_ids: [],
        },
        {
            id: 8,
            name: "Task 8",
            planned_date_begin: "2021-10-18 07:29:59",
            date_deadline: "2021-10-20 07:29:59",
            project_id: 1,
            user_ids: [2],
            depend_on_ids: [7],
        },
    ];
});

test("Connectors are correctly computed and rendered.", async () => {
    expect.assertions(14);

    mockDate("2021-10-10 7:00:00");

    /** @type {Map<ConnectorTaskIds, keyof typeof COLORS>} */
    const testMap = new Map([
        ["[1,2,2,2]", "default"],
        ["[3,2,4,2]", "default"],
        ["[5,2,6,2]", "error"],
        ["[7,2,8,2]", "warning"],
    ]);

    const view = await mountGanttView(ganttViewParams);
    const renderer = findComponent(view, (c) => c instanceof TaskGanttRenderer);

    const connectorMap = getConnectorMap(renderer);

    for (const [testKey, colorCode] of testMap.entries()) {
        const [masterTaskId, masterTaskUserId, taskId, taskUserId] = JSON.parse(testKey);

        expect(connectorMap.has(testKey)).toBe(true, {
            message: `There should be a connector between task ${masterTaskId} from group user ${masterTaskUserId} and task ${taskId} from group user ${taskUserId}.`,
        });
        const connector = connectorMap.get(testKey);
        const connectorColor = connector.style?.stroke?.color;
        const { color } = COLORS[colorCode];
        if (connectorColor) {
            expect(connectorColor).toBe(color, {
                message: `Connector props style should be "${colorCode}".`,
            });
        } else {
            expect(connectorColor).toBe(undefined, {
                message: "Connector props style should be the default one.",
            });
        }

        expect(getConnectorStroke(connector.id)).toHaveAttribute("stroke", color);
    }

    expect(testMap.size).toBe(connectorMap.size);
    expect(SELECTORS.connector).toHaveCount(testMap.size);
});

test("Connector dotted/dashed when depended task in closed state.", async () => {
    mockDate("2021-10-10 7:00:00");
    onRpc("get_all_deadlines", () => ({ milestone_id: [], project_id: [] }));

    // Taking only records for easier finding of dashed connecter
    projectModels.ProjectTask._records.length = 2;
    projectModels.ProjectTask._records[0].is_closed = true;

    await mountGanttView({
        ...ganttViewParams,
    });

    expect(".o_gantt_connector .o_connector_stroke_hover_ease").toHaveAttribute(
        "stroke-dasharray",
        "10 5"
    );
    expect(".o_gantt_connector .o_connector_stroke_outline").toHaveAttribute(
        "stroke-dasharray",
        "10 5"
    );
    expect(".o_gantt_connector .o_connector_stroke").toHaveAttribute("stroke-dasharray", "10 5");
});

test("Hovering a connector should cause the connected pills to get highlighted in task gantt.", async () => {
    mockDate("2021-10-10 7:00:00");
    await mountGanttView(ganttViewParams);
    expect(SELECTORS.highlightedPill).toHaveCount(0);

    await hover(getConnectorStroke(1));

    expect(SELECTORS.highlightedPill).toHaveCount(2);
});
