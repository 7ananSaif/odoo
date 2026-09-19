import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click, queryAll, queryAllTexts, queryFirst } from "@odoo/hoot-dom";
import { animationFrame, mockDate } from "@odoo/hoot-mock";
import {
    contains,
    defineParams,
    fields,
    getService,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { Tasks, Project, defineGanttModels } from "./gantt_mock_models";
import {
    SELECTORS,
    focusToday,
    ganttControlsChanges,
    getGridContent,
    mountGanttView,
    selectCustomRange,
    selectRange,
} from "./web_gantt_test_helpers";

import { browser } from "@web/core/browser/browser";
import { Domain } from "@web/core/domain";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { WebClient } from "@web/webclient/webclient";

describe.current.tags("desktop");

defineGanttModels();
beforeEach(() => {
    mockDate("2018-12-20T08:00:00", +1);
    defineParams({
        lang_parameters: {
            time_format: "%I:%M:%S",
        },
    });
});

test("empty ungrouped gantt rendering", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" />`,
        domain: [["id", "=", 0]],
    });
    const { viewTitle, range, columnHeaders, rows } = getGridContent();
    expect(viewTitle).toBe(null);
    expect(range).toBe("From: 12/01/2018 to: 02/28/2019");
    expect(columnHeaders).toHaveLength(29);
    expect(rows).toEqual([{}]);
    expect(SELECTORS.noContentHelper).toHaveCount(0);
    expect(queryFirst(".o_gantt_cell").offsetHeight).toBe(35, {
        message: "row height is 35px (25 * 1 pill height + 10px of default empty space)",
    });
});

test("ungrouped gantt rendering", async () => {
    const task2 = Tasks._records[1];
    const startDateLocalString = deserializeDateTime(task2.start).toFormat("f");
    const stopDateLocalString = deserializeDateTime(task2.stop).toFormat("f");
    Tasks._views.gantt = `<gantt date_start="start" date_stop="stop"/>`;

    onRpc("get_gantt_data", ({ model }) => expect.step(model));
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "tasks",
        type: "ir.actions.act_window",
        views: [[false, "gantt"]],
    });
    expect.verifySteps(["tasks"]);
    await animationFrame();

    const { viewTitle, range, columnHeaders, rows } = getGridContent();
    expect(viewTitle).toBe(null);
    expect(range).toBe("From: 12/01/2018 to: 02/28/2019");
    expect(columnHeaders).toHaveLength(29);
    expect(SELECTORS.expandCollapseButtons).not.toBeVisible();
    expect(rows).toEqual([
        {
            pills: [
                {
                    title: "Task 5",
                    level: 0,
                    colSpan: "01 December 2018 -> 04 (1/2) December 2018",
                },
                { title: "Task 1", level: 1, colSpan: "01 December 2018 -> Out of bounds (63) " },
                {
                    title: "Task 2",
                    level: 0,
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                },
                {
                    title: "Task 4",
                    level: 2,
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                },
                {
                    title: "Task 7",
                    level: 2,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
                { title: "Task 3", level: 0, colSpan: "27 December 2018 -> Out of bounds (68) " },
            ],
        },
    ]);

    expect(queryFirst(".o_gantt_cell").offsetHeight).toBe(85, {
        message: "row height is 85px (25 * 3 pills + 10px of default empty space)",
    });

    // test popover and local timezone
    expect(`.o_popover`).toHaveCount(0);
    const task2Pill = queryAll(SELECTORS.pill)[2];
    expect(task2Pill).toHaveText("Task 2");

    await contains(task2Pill).click();
    expect(`.o_popover`).toHaveCount(1);
    expect(queryAllTexts`.o_popover .popover-body span`).toEqual([
        "Task 2",
        startDateLocalString,
        stopDateLocalString,
    ]);

    await contains(`.o_popover .popover-footer i.fa.fa-close`).click();
    expect(`.o_popover`).toHaveCount(0);
});

test("ordered gantt view", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" progress="progress"/>`,
        groupBy: ["stage_id"],
    });
    const { viewTitle, range, columnHeaders, rows } = getGridContent();
    expect(viewTitle).toBe("Gantt View");
    expect(range).toBe("From: 12/01/2018 to: 02/28/2019");
    expect(columnHeaders).toHaveLength(29);
    expect(SELECTORS.noContentHelper).toHaveCount(0);
    expect(rows).toEqual([
        {
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 (1/2) December 2018",
                    level: 0,
                    title: "Task 5",
                },
            ],
            title: "todo",
        },
        {
            title: "in_progress",
            pills: [
                { level: 0, colSpan: "01 December 2018 -> Out of bounds (63) ", title: "Task 1" },
                {
                    level: 1,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    title: "Task 7",
                },
            ],
        },
        {
            title: "done",
            pills: [
                {
                    level: 0,
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    title: "Task 2",
                },
            ],
        },
        {
            title: "cancel",
            pills: [
                {
                    level: 0,
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    title: "Task 4",
                },
                { level: 0, colSpan: "27 December 2018 -> Out of bounds (68) ", title: "Task 3" },
            ],
        },
    ]);
});

test("empty single-level grouped gantt rendering", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
        groupBy: ["project_id"],
        domain: Domain.FALSE.toList(),
    });
    const { viewTitle, range, columnHeaders, rows } = getGridContent();
    expect(viewTitle).toBe("Gantt View");
    expect(range).toBe("From: 12/01/2018 to: 02/28/2019");
    expect(columnHeaders).toHaveLength(29);
    expect(rows).toEqual([{ title: "" }]);
    expect(SELECTORS.noContentHelper).toHaveCount(0);
});

test("single-level grouped gantt rendering", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop"/>`,
        groupBy: ["project_id"],
    });
    expect(SELECTORS.expandCollapseButtons).not.toBeVisible();

    const { range, viewTitle, columnHeaders, rows } = getGridContent();
    expect(range).toBe("From: 12/01/2018 to: 02/28/2019");
    expect(viewTitle).toBe("Tasks");
    expect(columnHeaders).toHaveLength(29);
    expect(rows).toEqual([
        {
            title: "Project 1",
            pills: [
                {
                    title: "Task 1",
                    colSpan: "01 December 2018 -> Out of bounds (63) ",
                    level: 0,
                },
                {
                    title: "Task 2",
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 1,
                },
                {
                    title: "Task 4",
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 2,
                },
                {
                    title: "Task 3",
                    colSpan: "27 December 2018 -> Out of bounds (68) ",
                    level: 1,
                },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 (1/2) December 2018",
                    level: 0,
                    title: "Task 5",
                },
                {
                    title: "Task 7",
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 0,
                },
            ],
        },
    ]);
});

test("display the field's falsy_value_label for false group, if defined", async () => {
    Tasks._fields.project_id.falsy_value_label = "I'm the false group";
    Tasks._records[0].project_id = false;

    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop"/>`,
        groupBy: ["project_id"],
    });

    expect(queryAllTexts(".o_gantt_row_header")).toEqual([
        "I'm the false group",
        "Project 1",
        "Project 2",
    ]);
});

test("single-level grouped gantt rendering with group_expand", async () => {
    const groups = [
        { project_id: [20, "Unused Project 1"], "id:array_agg": [] },
        { project_id: [50, "Unused Project 2"], "id:array_agg": [] },
        { project_id: [2, "Project 2"], "id:array_agg": [5, 7] },
        { project_id: [30, "Unused Project 3"], "id:array_agg": [] },
        { project_id: [1, "Project 1"], "id:array_agg": [1, 2, 3, 4] },
    ];
    patchWithCleanup(Tasks.prototype, {
        formatted_read_group: () => groups,
    });

    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop"/>`,
        groupBy: ["project_id"],
    });
    expect(SELECTORS.expandCollapseButtons).not.toBeVisible();

    const { range, viewTitle, columnHeaders, rows } = getGridContent();
    expect(range).toBe("From: 12/01/2018 to: 02/28/2019");
    expect(viewTitle).toBe("Tasks");
    expect(columnHeaders).toHaveLength(29);
    expect(rows).toEqual([
        { title: "Unused Project 1" },
        { title: "Unused Project 2" },
        {
            title: "Project 2",
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 (1/2) December 2018",
                    level: 0,
                    title: "Task 5",
                },
                {
                    title: "Task 7",
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 0,
                },
            ],
        },
        { title: "Unused Project 3" },
        {
            title: "Project 1",
            pills: [
                {
                    title: "Task 1",
                    colSpan: "01 December 2018 -> Out of bounds (63) ",
                    level: 0,
                },
                {
                    title: "Task 2",
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 1,
                },
                {
                    title: "Task 4",
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 2,
                },
                {
                    title: "Task 3",
                    colSpan: "27 December 2018 -> Out of bounds (68) ",
                    level: 1,
                },
            ],
        },
    ]);
});

test("multi-level grouped gantt rendering", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop"/>`,
        groupBy: ["user_id", "project_id", "stage"],
    });
    expect(SELECTORS.expandButton).toHaveCount(0);
    expect(SELECTORS.collapseButton).toHaveCount(1);

    const { range, viewTitle, columnHeaders, rows } = getGridContent();
    expect(range).toBe("From: 12/01/2018 to: 02/28/2019");
    expect(viewTitle).toBe("Tasks");
    expect(columnHeaders).toHaveLength(29);
    expect(rows).toEqual([
        {
            title: "User 1",
            isGroup: true,
            pills: [
                { title: "2", colSpan: "01 December 2018 -> 04 (1/2) December 2018" },
                { title: "1", colSpan: "04 (1/2) December 2018 -> 19 December 2018" },
                { title: "2", colSpan: "20 December 2018 -> 20 (1/2) December 2018" },
                { title: "1", colSpan: "20 (1/2) December 2018 -> Out of bounds (63) " },
            ],
        },
        {
            title: "Project 1",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "01 December 2018 -> 19 December 2018" },
                { title: "2", colSpan: "20 December 2018 -> 20 (1/2) December 2018" },
                { title: "1", colSpan: "20 (1/2) December 2018 -> Out of bounds (63) " },
            ],
        },
        {
            title: "To Do",
            pills: [
                { title: "Task 1", colSpan: "01 December 2018 -> Out of bounds (63) ", level: 0 },
            ],
        },
        {
            title: "In Progress",
            pills: [
                {
                    title: "Task 4",
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 0,
                },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 (1/2) December 2018",
                    title: "1",
                },
            ],
            isGroup: true,
        },
        {
            title: "Done",
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 (1/2) December 2018",
                    level: 0,
                    title: "Task 5",
                },
            ],
        },
        {
            title: "User 2",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "17 (1/2) December 2018 -> 20 (1/2) December 2018" },
                { title: "2", colSpan: "20 (1/2) December 2018 -> 20 December 2018" },
                { title: "1", colSpan: "21 December 2018 -> 22 (1/2) December 2018" },
                { title: "1", colSpan: "27 December 2018 -> Out of bounds (68) " },
            ],
        },
        {
            title: "Project 1",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018" },
                { title: "1", colSpan: "27 December 2018 -> Out of bounds (68) " },
            ],
        },
        {
            title: "Done",
            pills: [
                {
                    title: "Task 2",
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                },
            ],
        },
        {
            title: "Cancelled",
            pills: [
                { title: "Task 3", colSpan: "27 December 2018 -> Out of bounds (68) ", level: 0 },
            ],
        },
        {
            title: "Project 2",
            isGroup: true,
            pills: [{ title: "1", colSpan: "20 (1/2) December 2018 -> 20 December 2018" }],
        },
        {
            title: "Cancelled",
            pills: [
                {
                    title: "Task 7",
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 0,
                },
            ],
        },
    ]);
    expect(`.o_gantt_group_pill .o_gantt_consolidated_pill`).toHaveStyle({
        backgroundColor: "rgb(113, 75, 103)",
    });
});

test("many2many grouped gantt rendering", async () => {
    Tasks._fields.user_ids = fields.Many2many({ string: "Assignees", relation: "res.users" });
    Tasks._records[0].user_ids = [1, 2];

    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop"/>`,
        groupBy: ["user_ids"],
    });
    expect(SELECTORS.expandCollapseButtons).not.toBeVisible();

    const { range, viewTitle, columnHeaders, rows } = getGridContent();
    expect(range).toBe("From: 12/01/2018 to: 02/28/2019");
    expect(viewTitle).toBe("Tasks");
    expect(columnHeaders).toHaveLength(29);
    expect(rows).toEqual([
        {
            title: "Undefined Assignees",
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 (1/2) December 2018",
                    level: 0,
                    title: "Task 5",
                },
                {
                    title: "Task 2",
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                },
                {
                    title: "Task 4",
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 1,
                },
                {
                    title: "Task 7",
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 1,
                },
                { title: "Task 3", colSpan: "27 December 2018 -> Out of bounds (68) ", level: 0 },
            ],
        },
        {
            title: "User 1",
            pills: [
                { title: "Task 1", colSpan: "01 December 2018 -> Out of bounds (63) ", level: 0 },
            ],
        },
        {
            title: "User 2",
            pills: [
                { title: "Task 1", colSpan: "01 December 2018 -> Out of bounds (63) ", level: 0 },
            ],
        },
    ]);
});

test("multi-level grouped with many2many field in gantt view", async () => {
    Tasks._fields.user_ids = fields.Many2many({ string: "Assignees", relation: "res.users" });
    Tasks._records[0].user_ids = [1, 2];

    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop"/>`,
        groupBy: ["user_ids", "project_id"],
    });
    expect(SELECTORS.expandButton).toHaveCount(0);
    expect(SELECTORS.collapseButton).toHaveCount(1);

    const { range, viewTitle, columnHeaders, rows } = getGridContent();
    expect(range).toBe("From: 12/01/2018 to: 02/28/2019");
    expect(viewTitle).toBe("Tasks");
    expect(columnHeaders).toHaveLength(29);
    expect(rows).toEqual([
        {
            title: "Undefined Assignees",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "01 December 2018 -> 04 (1/2) December 2018" },
                { title: "1", colSpan: "17 (1/2) December 2018 -> 19 December 2018" },
                { title: "2", colSpan: "20 December 2018 -> 20 (1/2) December 2018" },
                { title: "2", colSpan: "20 (1/2) December 2018 -> 20 December 2018" },
                { title: "1", colSpan: "21 December 2018 -> 22 (1/2) December 2018" },
                { title: "1", colSpan: "27 December 2018 -> Out of bounds (68) " },
            ],
        },
        {
            title: "Project 1",
            pills: [
                {
                    title: "Task 2",
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                },
                {
                    title: "Task 4",
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 1,
                },
                { title: "Task 3", colSpan: "27 December 2018 -> Out of bounds (68) ", level: 0 },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 (1/2) December 2018",
                    level: 0,
                    title: "Task 5",
                },
                {
                    title: "Task 7",
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 0,
                },
            ],
        },
        {
            title: "User 1",
            isGroup: true,
            pills: [{ title: "1", colSpan: "01 December 2018 -> Out of bounds (63) " }],
        },
        {
            title: "Project 1",
            pills: [
                { title: "Task 1", colSpan: "01 December 2018 -> Out of bounds (63) ", level: 0 },
            ],
        },
        {
            title: "User 2",
            isGroup: true,
            pills: [{ title: "1", colSpan: "01 December 2018 -> Out of bounds (63) " }],
        },
        {
            title: "Project 1",
            pills: [
                { title: "Task 1", colSpan: "01 December 2018 -> Out of bounds (63) ", level: 0 },
            ],
        },
    ]);
});

test("full precision gantt rendering", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" default_range="week" date_stop="stop" precision="{'day':'hour:full', 'week':'day:full', 'month':'day:full'}"/>`,
        groupBy: ["user_id", "project_id"],
    });
    expect(SELECTORS.expandButton).toHaveCount(0);
    expect(SELECTORS.collapseButton).toHaveCount(1);

    const { range, viewTitle, columnHeaders, rows } = getGridContent();
    expect(range).toBe("Week");
    expect(viewTitle).toBe("Gantt View");
    expect(columnHeaders).toHaveLength(9);
    expect(rows).toEqual([
        {
            title: "User 1",
            isGroup: true,
            pills: [
                {
                    title: "1",
                    colSpan: "Out of bounds (1)  -> Wednesday 19 Week 51, Dec 16 - Dec 22",
                },
                {
                    title: "2",
                    colSpan:
                        "Thursday 20 Week 51, Dec 16 - Dec 22 -> Thursday 20 Week 51, Dec 16 - Dec 22",
                },
                {
                    title: "1",
                    colSpan: "Friday 21 Week 51, Dec 16 - Dec 22 -> Out of bounds (22) ",
                },
            ],
        },
        {
            title: "Project 1",
            pills: [
                { level: 0, colSpan: "Out of bounds (1)  -> Out of bounds (22) ", title: "Task 1" },
                {
                    level: 1,
                    colSpan:
                        "Thursday 20 Week 51, Dec 16 - Dec 22 -> Thursday 20 Week 51, Dec 16 - Dec 22",
                    title: "Task 4",
                },
            ],
        },
        {
            title: "User 2",
            isGroup: true,
            pills: [
                {
                    title: "1",
                    colSpan:
                        "Monday 17 Week 51, Dec 16 - Dec 22 -> Wednesday 19 Week 51, Dec 16 - Dec 22",
                },
                {
                    title: "2",
                    colSpan:
                        "Thursday 20 Week 51, Dec 16 - Dec 22 -> Thursday 20 Week 51, Dec 16 - Dec 22",
                },
                {
                    title: "1",
                    colSpan:
                        "Friday 21 Week 51, Dec 16 - Dec 22 -> Saturday 22 Week 51, Dec 16 - Dec 22",
                },
            ],
        },
        {
            title: "Project 1",
            pills: [
                {
                    level: 0,
                    colSpan:
                        "Monday 17 Week 51, Dec 16 - Dec 22 -> Saturday 22 Week 51, Dec 16 - Dec 22",
                    title: "Task 2",
                },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    level: 0,
                    colSpan:
                        "Thursday 20 Week 51, Dec 16 - Dec 22 -> Thursday 20 Week 51, Dec 16 - Dec 22",
                    title: "Task 7",
                },
            ],
        },
    ]);
});

test("gantt rendering, thumbnails", async () => {
    onRpc("get_gantt_data", () => ({
        groups: [
            {
                user_id: [1, "User 1"],
                __record_ids: [1],
            },
            {
                user_id: false,
                __record_ids: [2],
            },
        ],
        length: 2,
        records: [
            {
                display_name: "Task 1",
                id: 1,
                start: "2018-11-30 18:30:00",
                stop: "2018-12-31 18:29:59",
            },
            {
                display_name: "Task 2",
                id: 2,
                start: "2018-12-01 18:30:00",
                stop: "2018-12-02 18:29:59",
            },
        ],
    }));
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" thumbnails="{'user_id': 'image'}"/>`,
        groupBy: ["user_id"],
    });
    expect(SELECTORS.thumbnail).toHaveCount(1);
    expect(SELECTORS.thumbnail).toHaveAttribute(
        "data-src",
        /web\/image\?model=res\.users&id=1&field=image/
    );
});

test("gantt rendering, pills must be chronologically ordered", async () => {
    onRpc("get_gantt_data", () => ({
        groups: [
            {
                user_id: [1, "User 1"],
                __record_ids: [1],
            },
            {
                user_id: false,
                __record_ids: [2],
            },
        ],
        length: 2,
        records: [
            {
                display_name: "Task 14:30:00",
                id: 1,
                start: "2018-12-17 14:30:00",
                stop: "2018-12-17 18:29:59",
            },
            {
                display_name: "Task 08:30:00",
                id: 2,
                start: "2018-12-17 08:30:00",
                stop: "2018-12-17 13:29:59",
            },
        ],
    }));
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" default_range="week" date_start="start" date_stop="stop" thumbnails="{'user_id': 'image'}"/>`,
    });
    const { rows } = getGridContent();
    expect(rows).toEqual([
        {
            pills: [
                {
                    title: "Task 08:30:00",
                    level: 0,
                    colSpan:
                        "Monday 17 Week 51, Dec 16 - Dec 22 -> Monday 17 Week 51, Dec 16 - Dec 22",
                },
                {
                    title: "Task 14:30:00",
                    level: 1,
                    colSpan:
                        "Monday 17 (1/2) Week 51, Dec 16 - Dec 22 -> Monday 17 Week 51, Dec 16 - Dec 22",
                },
            ],
        },
    ]);
});

test("range switching", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
    });
    expect(SELECTORS.expandCollapseButtons).not.toBeVisible();
    let gridContent = getGridContent();
    expect(gridContent.range).toBe("From: 12/01/2018 to: 02/28/2019");
    expect(gridContent.columnHeaders).toHaveLength(29);
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    title: "Task 5",
                    level: 0,
                    colSpan: "01 December 2018 -> 04 (1/2) December 2018",
                },
                { title: "Task 1", level: 1, colSpan: "01 December 2018 -> Out of bounds (63) " },
                {
                    title: "Task 2",
                    level: 0,
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                },
                {
                    title: "Task 4",
                    level: 2,
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                },
                {
                    title: "Task 7",
                    level: 2,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
                { title: "Task 3", level: 0, colSpan: "27 December 2018 -> Out of bounds (68) " },
            ],
        },
    ]);

    await selectRange("Day");
    await focusToday();
    await ganttControlsChanges();
    expect(SELECTORS.expandCollapseButtons).not.toBeVisible();
    gridContent = getGridContent();
    expect(gridContent.range).toBe("Day");
    expect(gridContent.columnHeaders).toHaveLength(42);
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    title: "Task 1",
                    level: 0,
                    colSpan: "Out of bounds (1)  -> Out of bounds (73) ",
                },
                {
                    title: "Task 2",
                    level: 1,
                    colSpan: "Out of bounds (1)  -> Out of bounds (73) ",
                },
                {
                    title: "Task 4",
                    level: 2,
                    colSpan: "3am December 20, 2018 -> 7am December 20, 2018",
                },
                {
                    title: "Task 7",
                    level: 2,
                    colSpan: "1pm December 20, 2018 -> 7pm December 20, 2018",
                },
            ],
        },
    ]);

    await selectRange("Week");
    await focusToday();
    await ganttControlsChanges();
    expect(SELECTORS.expandCollapseButtons).not.toBeVisible();
    gridContent = getGridContent();
    expect(gridContent.range).toBe("Week");
    expect(gridContent.columnHeaders).toHaveLength(9);
    expect(gridContent.rows).toEqual([
        {
            pills: [
                { title: "Task 1", level: 0, colSpan: "Out of bounds (1)  -> Out of bounds (43) " },
                {
                    title: "Task 2",
                    level: 1,
                    colSpan: "Out of bounds (18)  -> Saturday 22 (1/2) Week 51, Dec 16 - Dec 22",
                },
                {
                    title: "Task 4",
                    level: 2,
                    colSpan:
                        "Thursday 20 Week 51, Dec 16 - Dec 22 -> Thursday 20 (1/2) Week 51, Dec 16 - Dec 22",
                },
                {
                    title: "Task 7",
                    level: 2,
                    colSpan:
                        "Thursday 20 (1/2) Week 51, Dec 16 - Dec 22 -> Thursday 20 Week 51, Dec 16 - Dec 22",
                },
                {
                    colSpan: "Thursday 27 Week 52, Dec 23 - Dec 29 -> Out of bounds (43) ",
                    level: 1,
                    title: "Task 3",
                },
            ],
        },
    ]);

    await selectRange("Month");
    await focusToday();
    await ganttControlsChanges();
    expect(SELECTORS.expandCollapseButtons).not.toBeVisible();
    gridContent = getGridContent();
    expect(gridContent.range).toBe("Month");
    expect(gridContent.columnHeaders).toHaveLength(32);
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    title: "Task 1",
                    level: 1,
                    colSpan: "Out of bounds (60)  -> 31 December 2018",
                },
                {
                    title: "Task 2",
                    level: 0,
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                },
                {
                    title: "Task 4",
                    level: 2,
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                },
                {
                    title: "Task 7",
                    level: 2,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
                { title: "Task 3", level: 0, colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
    ]);

    await selectRange("Year");
    await focusToday();
    await ganttControlsChanges();
    expect(SELECTORS.expandCollapseButtons).not.toBeVisible();
    gridContent = getGridContent();
    expect(gridContent.range).toBe("Year");
    expect(gridContent.columnHeaders).toHaveLength(16);
    expect(gridContent.rows).toEqual([
        {
            pills: [
                { title: "Task 5", level: 0, colSpan: "November 2018 -> December 2018" },
                { title: "Task 6", level: 1, colSpan: "November 2018 -> November 2018" },
                { title: "Task 1", level: 2, colSpan: "November 2018 -> December 2018" },
                { title: "Task 2", level: 1, colSpan: "December 2018 -> December 2018" },
                { title: "Task 4", level: 3, colSpan: "December 2018 -> December 2018" },
                { title: "Task 7", level: 4, colSpan: "December 2018 -> December 2018" },
                { title: "Task 3", level: 5, colSpan: "December 2018 -> January 2019" },
            ],
        },
    ]);
});

test("today is highlighted", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
    });
    expect(`.o_gantt_header_cell.o_gantt_today`).toHaveCount(1);
    expect(`.o_gantt_header_cell.o_gantt_today`).toHaveText("20");
});

test("current month is highlighted'", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" default_range="year"/>',
    });
    expect(`.o_gantt_header_cell.o_gantt_today`).toHaveCount(1);
    expect(`.o_gantt_header_cell.o_gantt_today`).toHaveText("December");
});

test("current hour is highlighted'", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" default_range="day"/>',
    });
    expect(`.o_gantt_header_cell.o_gantt_today`).toHaveCount(1);
    expect(`.o_gantt_header_cell.o_gantt_today`).toHaveText("9\nam");
});

test("Day scale with 12-hours format", async () => {
    defineParams({
        lang_parameters: {
            time_format: "%I:%M:%S",
        },
    });

    await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
        context: {
            default_start_date: "2018-12-20",
            default_stop_date: "2018-12-20",
        },
    });
    const { columnHeaders, range } = getGridContent();
    expect(range).toBe("From: 12/20/2018 to: 12/20/2018");
    expect(columnHeaders.slice(0, 4).map((h) => h.title)).toEqual(["12am", "1am", "2am", "3am"]);
    expect(columnHeaders.slice(12, 16).map((h) => h.title)).toEqual(["12pm", "1pm", "2pm", "3pm"]);
});

test("Day scale with 24-hours format", async () => {
    defineParams({
        lang_parameters: {
            time_format: "%H:%M:%S",
        },
    });

    await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
        context: {
            default_start_date: "2018-12-20",
            default_stop_date: "2018-12-20",
        },
    });

    const { columnHeaders, range } = getGridContent();
    expect(range).toBe("From: 12/20/2018 to: 12/20/2018");
    expect(columnHeaders.slice(0, 4).map((h) => h.title)).toEqual(["0", "1", "2", "3"]);
    expect(columnHeaders.slice(12, 16).map((h) => h.title)).toEqual(["12", "13", "14", "15"]);
});

test("group tasks by task_properties", async () => {
    Project._fields.properties_definitions = fields.PropertiesDefinition();
    Project._records[0].properties_definitions = [
        {
            name: "bd6404492c244cff",
            type: "char",
        },
    ];
    Tasks._fields.task_properties = fields.Properties({
        definition_record: "project_id",
        definition_record_field: "properties_definitions",
    });
    Tasks._records = [
        {
            id: 1,
            name: "Blop",
            start: "2018-12-14 08:00:00",
            stop: "2018-12-24 08:00:00",
            user_id: 1,
            project_id: 1,
            task_properties: {
                bd6404492c244cff: "test value 1",
            },
        },
        {
            id: 2,
            name: "Yop",
            start: "2018-12-02 08:00:00",
            stop: "2018-12-12 08:00:00",
            user_id: 2,
            project_id: 1,
            task_properties: {
                bd6404492c244cff: "test value 1",
            },
        },
    ];
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop"/>',
        groupBy: ["task_properties.bd6404492c244cff"],
    });
    const { rows } = getGridContent();
    expect(rows).toEqual([
        {
            pills: [
                {
                    title: "Yop",
                    colSpan: "02 December 2018 -> 12 (1/2) December 2018",
                    level: 0,
                },
                {
                    title: "Blop",
                    colSpan: "14 December 2018 -> 24 (1/2) December 2018",
                    level: 0,
                },
            ],
        },
    ]);
});

test("group tasks by date", async () => {
    Tasks._fields.my_date = fields.Date({ string: "My date" });
    Tasks._records = [
        {
            id: 1,
            name: "Blop",
            start: "2018-12-14 08:00:00",
            stop: "2018-12-24 08:00:00",
            user_id: 1,
            project_id: 1,
        },
        {
            id: 2,
            name: "Yop",
            start: "2018-12-02 08:00:00",
            stop: "2018-12-12 08:00:00",
            user_id: 2,
            project_id: 1,
        },
    ];
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop"/>',
        groupBy: ["my_date:month"],
    });
    const { rows } = getGridContent();
    expect(rows).toEqual([
        {
            pills: [
                {
                    title: "Yop",
                    colSpan: "02 December 2018 -> 12 (1/2) December 2018",
                    level: 0,
                },
                {
                    title: "Blop",
                    colSpan: "14 December 2018 -> 24 (1/2) December 2018",
                    level: 0,
                },
            ],
        },
    ]);
});

test("Scale: scale default is fetched from localStorage", async () => {
    let view;
    patchWithCleanup(browser.localStorage, {
        getItem(key) {
            if (String(key).startsWith("rangeOf-viewId")) {
                expect.step(`get_range_week`);
                return "week";
            }
        },
        setItem(key, value) {
            if (view && key === `rangeOf-viewId-${view.env?.config?.viewId}`) {
                expect.step(`set_range_${value}`);
            }
        },
    });
    view = await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" default_range="week"/>',
    });
    expect(getGridContent().range).toBe("Week");
    await selectRange("Year");
    await ganttControlsChanges();
    expect(getGridContent().range).toBe("Year");
    expect.verifySteps(["get_range_week", "set_range_year"]);
});

test("initialization with default_start_date only", async (assert) => {
    await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        context: { default_start_date: "2028-04-25" },
    });
    const { range, columnHeaders, groupHeaders } = getGridContent();
    expect(range).toBe("From: 04/25/2028 to: 06/30/2028");
    expect(columnHeaders.slice(0, 7).map((h) => h.title)).toEqual([
        "25",
        "26",
        "27",
        "28",
        "29",
        "30",
        "01",
    ]);
    expect(groupHeaders.map((h) => h.title)).toEqual(["April 2028", "May 2028"]);
});

test("initialization with default_stop_date only", async (assert) => {
    await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        context: { default_stop_date: "2028-04-25" },
    });
    const { range, columnHeaders, groupHeaders } = getGridContent();
    expect(range).toBe("From: 02/01/2028 to: 04/25/2028");
    expect(
        columnHeaders.slice(columnHeaders.length - 7, columnHeaders.length).map((h) => h.title)
    ).toEqual(["19", "20", "21", "22", "23", "24", "25"]);
    expect(groupHeaders.map((h) => h.title)).toEqual(["March 2028", "April 2028"]);
});

test("initialization with default_start_date and default_stop_date", async (assert) => {
    await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        context: {
            default_start_date: "2017-01-29",
            default_stop_date: "2019-05-26",
        },
    });
    const { range, groupHeaders } = getGridContent();
    expect(range).toBe("From: 01/29/2017 to: 05/26/2019");
    expect(groupHeaders.map((h) => h.title)).toEqual(["2017", "2018", "2019"]);
    expect(`${SELECTORS.columnHeader}.o_gantt_today`).toHaveCount(1);
});

test("switch startDate and stopDate if not in <= relation", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
    });
    expect(getGridContent().range).toBe("From: 12/01/2018 to: 02/28/2019");
    await selectCustomRange({ startDate: "2019-03-01" });
    expect(getGridContent().range).toBe("From: 03/01/2019 to: 03/01/2019");
    await selectCustomRange({ stopDate: "2019-02-28" });
    expect(getGridContent().range).toBe("From: 02/28/2019 to: 02/28/2019");
});

test("range will not exceed 10 years", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt date_start="start" date_stop="stop"/>
        `,
    });
    expect(getGridContent().range).toBe("From: 12/01/2018 to: 02/28/2019");
    await selectCustomRange({ startDate: "2006-02-28" });
    expect(getGridContent().range).toBe("From: 02/28/2006 to: 02/27/2016");
    await selectCustomRange({ stopDate: "2020-02-28" });
    expect(getGridContent().range).toBe("From: 03/01/2010 to: 02/28/2020");
});

test("range with identical startDate and stopDate", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt date_start="start" date_stop="stop"/>
        `,
    });
    expect(getGridContent().range).toBe("From: 12/01/2018 to: 02/28/2019");
    await selectCustomRange({ startDate: "2019-03-28", stopDate: "2019-03-28" });
    expect(getGridContent().range).toBe("From: 03/28/2019 to: 03/28/2019");
    await focusToday();
    await ganttControlsChanges();
    expect(getGridContent().range).toBe("From: 12/20/2018 to: 12/20/2018");
});

test("popover-template with an added footer", async () => {
    expect.assertions(9);
    onRpc("unlink", ({ model, method, args }) => {
        expect(model).toBe("tasks");
        expect(method).toBe("unlink");
        expect(args).toEqual([[2]]);
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt date_start="start" date_stop="stop">
                <templates>
                    <t t-name="gantt-popover">
                        Content
                        <footer replace="0">
                            <button name="unlink" type="object" string="Delete" icon="fa-trash" class="btn btn-sm btn-secondary"/>
                        </footer>
                    </t>
                </templates>
            </gantt>
        `,
        domain: [["id", "=", 2]],
    });
    expect(SELECTORS.pill).toHaveCount(1);
    expect(".o_popover").toHaveCount(0);

    await click(SELECTORS.pill);
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover .popover-footer button").toHaveCount(2);
    expect(queryAllTexts(".o_popover .popover-footer button")).toEqual(["Edit", "Delete"]);

    await click(".o_popover .popover-footer button:last-child");
    await animationFrame();
    expect(SELECTORS.pill).toHaveCount(0);
});

test("popover-template with a replaced footer", async () => {
    expect.assertions(9);
    onRpc("unlink", ({ model, method, args }) => {
        expect(model).toBe("tasks");
        expect(method).toBe("unlink");
        expect(args).toEqual([[2]]);
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt date_start="start" date_stop="stop">
                <templates>
                    <t t-name="gantt-popover">
                        Content
                        <footer>
                            <button name="unlink" type="object" string="Delete" icon="fa-trash" class="btn btn-sm btn-secondary"/>
                        </footer>
                    </t>
                </templates>
            </gantt>
        `,
        domain: [["id", "=", 2]],
    });
    expect(SELECTORS.pill).toHaveCount(1);
    expect(".o_popover").toHaveCount(0);

    await click(SELECTORS.pill);
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover .popover-footer button").toHaveCount(1);
    expect(".o_popover .popover-footer button").toHaveText("Delete");

    await click(".o_popover .popover-footer button");
    await animationFrame();
    expect(SELECTORS.pill).toHaveCount(0);
});

test("popover-template with a button in the body", async () => {
    expect.assertions(11);
    onRpc("unlink", ({ model, method, args }) => {
        expect(model).toBe("tasks");
        expect(method).toBe("unlink");
        expect(args).toEqual([[2]]);
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt date_start="start" date_stop="stop">
                <templates>
                    <t t-name="gantt-popover">
                        <button name="unlink" type="object" string="Delete" icon="fa-trash" class="btn btn-sm btn-secondary"/>
                    </t>
                </templates>
            </gantt>
        `,
        domain: [["id", "=", 2]],
    });
    expect(SELECTORS.pill).toHaveCount(1);
    expect(".o_popover").toHaveCount(0);

    await click(SELECTORS.pill);
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover .popover-body button").toHaveCount(1);
    expect(".o_popover .popover-footer button").toHaveCount(1);
    expect(".o_popover .popover-body button").toHaveText("Delete");
    expect(".o_popover .popover-footer button").toHaveText("Edit");

    await click(".o_popover .popover-body button");
    await animationFrame();
    expect(SELECTORS.pill).toHaveCount(0);
});

test("aggregation with half precision", async () => {
    Tasks._records = Tasks._records.slice(0, 2);
    Tasks._records[0].start = "2018-12-21 07:00:00";
    Tasks._records[0].stop = "2018-12-21 11:00:00";
    Tasks._records[1].start = "2018-12-21 07:00:00";
    Tasks._records[1].stop = "2018-12-21 16:00:00";
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt date_start="start" date_stop="stop" total_row="1" default_range="month" precision="{'month':'day:half'}" />
        `,
    });
    expect(getGridContent().rows).toEqual([
        {
            pills: [
                {
                    title: "Task 1",
                    colSpan: "21 December 2018 -> 21 (1/2) December 2018",
                    level: 0,
                },
                {
                    title: "Task 2",
                    colSpan: "21 December 2018 -> 21 December 2018",
                    level: 1,
                },
            ],
        },
        {
            isTotalRow: true,
            pills: [
                {
                    title: "2",
                    colSpan: "21 December 2018 -> 21 (1/2) December 2018",
                    level: 0,
                },
                {
                    title: "1",
                    colSpan: "21 (1/2) December 2018 -> 21 December 2018",
                    level: 0,
                },
            ],
        },
    ]);
});
