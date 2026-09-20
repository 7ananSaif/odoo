import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click, leave, queryAll, queryAllTexts, queryFirst, queryOne } from "@odoo/hoot-dom";
import { animationFrame, mockDate, runAllTimers } from "@odoo/hoot-mock";
import { contains, defineParams, onRpc } from "@web/../tests/web_test_helpers";
import { Tasks, defineGanttModels } from "./gantt_mock_models";
import {
    SELECTORS,
    clickCell,
    dragPill,
    getCell,
    getCellColorProperties,
    getGridContent,
    getPill,
    getPillWrapper,
    hoverGridCell,
    mountGanttView,
    resizePill,
    setCellParts,
} from "./web_gantt_test_helpers";

describe.current.tags("desktop");

defineGanttModels();
beforeEach(() => {
    mockDate("2018-12-20T07:00:00", +1);
    defineParams({
        lang_parameters: {
            time_format: "%I:%M:%S",
        },
    });
});

test("create attribute", async () => {
    Tasks._views.list = `<list><field name="name"/></list>`;
    Tasks._views.search = `<search><field name="name"/></search>`;
    onRpc("has_group", () => true);
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" create="0"/>`,
    });
    expect(".o_dialog").toHaveCount(0);
    await hoverGridCell("06", "December 2018");
    await clickCell("06", "December 2018");
    expect(".o_dialog").toHaveCount(1);
    expect(".modal-title").toHaveText("Plan");
    expect(".o_create_button").toHaveCount(0);
});

test("plan attribute", async () => {
    Tasks._views.form = `<form><field name="name"/></form>`;
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" plan="0"/>`,
    });
    expect(".o_dialog").toHaveCount(0);
    await hoverGridCell("06", "December 2018");
    await clickCell("06", "December 2018");
    expect(".o_dialog").toHaveCount(1);
    expect(".modal-title").toHaveText("Create");
});

test("edit attribute", async () => {
    Tasks._views.form = `<form><field name="name"/></form>`;
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" edit="0"/>`,
    });
    expect(SELECTORS.resizable).toHaveCount(0);
    expect(SELECTORS.draggable).toHaveCount(0);
    expect(getGridContent().rows).toEqual([
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

    await contains(getPill("Task 1")).click();
    expect(`.o_popover button.btn-primary`).toHaveText(/view/i);
    await contains(`.o_popover button.btn-primary`).click();
    expect(".modal .o_form_readonly").toHaveCount(1);
});

test("total_row attribute", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" total_row="1"/>`,
    });

    const { rows } = getGridContent();
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
        {
            isTotalRow: true,
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 (1/2) December 2018",
                    level: 0,
                    title: "2",
                },
                {
                    colSpan: "04 (1/2) December 2018 -> 17 (1/2) December 2018",
                    level: 0,
                    title: "1",
                },
                {
                    colSpan: "17 (1/2) December 2018 -> 19 December 2018",
                    level: 0,
                    title: "2",
                },
                {
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 0,
                    title: "3",
                },
                {
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 0,
                    title: "3",
                },
                {
                    colSpan: "21 December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                    title: "2",
                },
                {
                    colSpan: "22 (1/2) December 2018 -> 26 December 2018",
                    level: 0,
                    title: "1",
                },
                {
                    colSpan: "27 December 2018 -> Out of bounds (63) ",
                    level: 0,
                    title: "2",
                },
            ],
        },
    ]);
});

test("default_range attribute excluded from scales", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" default_range="day" scales="week"/>`,
    });
    const { columnHeaders, range } = getGridContent();
    expect(range).toBe("Day");
    expect(columnHeaders).toHaveLength(42);
});

test("default_range omitted, scales provided", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" scales="day,week"/>`,
    });
    const { columnHeaders, range } = getGridContent();
    expect(range).toBe("From: 12/01/2018 to: 02/28/2019");
    expect(columnHeaders).toHaveLength(9);

    await contains(SELECTORS.scaleSelectorToggler).click();
    await animationFrame();
    expect(`${SELECTORS.scaleSelectorMenu} .dropdown-item`).toHaveCount(3);
    expect(queryAllTexts(`${SELECTORS.scaleSelectorMenu} .dropdown-item`)).toEqual([
        "Day",
        "Week",
        "From\n12/01/2018\nto\n02/28/2019\nApply",
    ]);
});

test("scales attribute", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" scales="month,day,trololo"/>`,
    });
    const { columnHeaders, range } = getGridContent();
    expect(range).toBe("From: 12/01/2018 to: 02/28/2019");
    expect(columnHeaders).toHaveLength(29);

    await contains(SELECTORS.scaleSelectorToggler).click();
    await animationFrame();
    expect(queryAllTexts(`${SELECTORS.scaleSelectorMenu} .dropdown-item`)).toEqual([
        "Day",
        "Month",
        "From\n12/01/2018\nto\n02/28/2019\nApply",
    ]);
});

test("precision attribute ('day': 'hour:quarter')", async () => {
    onRpc("write", ({ args }) => expect.step(args));
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                precision="{'day': 'hour:quarter'}"
            />
        `,
        context: {
            default_start_date: "2018-12-20",
            default_stop_date: "2018-12-20",
        },
        domain: [["id", "=", 7]],
    });

    // resize of a quarter
    const dropHandle = await resizePill(getPillWrapper("Task 7"), "end", 0.25, false);
    await animationFrame();
    expect(SELECTORS.startBadge).toHaveText("1:30 PM");
    expect(SELECTORS.stopBadge).toHaveText("7:44 PM (+15 minutes)");

    // manually trigger the drop to trigger a write
    await dropHandle();
    await animationFrame();
    expect(SELECTORS.startBadge).toHaveCount(0);
    expect(SELECTORS.stopBadge).toHaveCount(0);
    expect.verifySteps([[[7], { stop: "2018-12-20 18:44:59" }]]);

    const { moveTo, drop } = await dragPill("Task 7");
    await moveTo({ columnHeader: "12pm", groupHeader: "December 20, 2018", part: 4 });
    expect(SELECTORS.startBadge).toHaveText("12:45 PM");
    expect(SELECTORS.stopBadge).toHaveText("6:59 PM");
    expect(SELECTORS.startBadge).toHaveClass("text-danger");
    expect(SELECTORS.stopBadge).toHaveClass("text-danger");
    await drop();
    expect.verifySteps([[[7], { start: "2018-12-20 11:45:12", stop: "2018-12-20 17:59:59" }]]);
});

test("precision attribute ('month': 'day:full')", async () => {
    onRpc("write", ({ args }) => expect.step(args));
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                precision="{'month': 'day:full'}"
            />
        `,
        domain: [["id", "=", 7]],
    });

    // resize of a quarter
    const dropHandle = await resizePill(getPillWrapper("Task 7"), "end", 2, false);
    await animationFrame();
    expect(SELECTORS.startBadge).toHaveText("12/20/2018");
    expect(SELECTORS.stopBadge).toHaveText("12/22/2018 (+48 hours)");

    // manually trigger the drop to trigger a write
    await dropHandle();
    await animationFrame();
    expect(SELECTORS.startBadge).toHaveCount(0);
    expect(SELECTORS.stopBadge).toHaveCount(0);
    expect.verifySteps([[[7], { stop: "2018-12-22 18:29:59" }]]);

    const { moveTo, drop } = await dragPill("Task 7");
    await moveTo({ columnHeader: "23", groupHeader: "December 2018" });
    expect(SELECTORS.startBadge).toHaveText("12/23/2018");
    expect(SELECTORS.stopBadge).toHaveText("12/25/2018");
    expect(SELECTORS.startBadge).toHaveClass("text-success");
    expect(SELECTORS.stopBadge).toHaveClass("text-success");
    await drop();
    expect.verifySteps([[[7], { start: "2018-12-23 12:30:12", stop: "2018-12-25 18:29:59" }]]);
});

test("progress attribute", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop" progress="progress"/>`,
        groupBy: ["project_id"],
    });
    expect(`${SELECTORS.pill} .o_gantt_progress`).toHaveCount(4);
    expect(
        queryAll(SELECTORS.pill).map((el) => ({
            text: el.innerText,
            progress: el.querySelector(".o_gantt_progress")?.style?.width || null,
        }))
    ).toEqual([
        { text: "Task 1", progress: null },
        { text: "Task 2", progress: "30%" },
        { text: "Task 4", progress: null },
        { text: "Task 3", progress: "60%" },
        { text: "Task 5", progress: "100%" },
        { text: "Task 7", progress: "80%" },
    ]);
});

test("form_view_id attribute", async () => {
    Tasks._views[["form", 42]] = `<form><field name="name"/></form>`;
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop" form_view_id="42"/>`,
        groupBy: ["project_id"],
    });
    onRpc("get_views", ({ kwargs }) => expect.step(["get_views", kwargs.views]));
    await contains(queryFirst(SELECTORS.addButton + ":visible")).click();
    expect(".modal .o_form_view").toHaveCount(1);
    expect.verifySteps([
        ["get_views", [[42, "form"]]], // get_views when form view dialog opens
    ]);
});

test("decoration attribute", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt date_start="start" date_stop="stop" decoration-info="stage == 'todo'">
                <field name="stage"/>
            '</gantt>
        `,
    });
    expect(getPill("Task 1")).toHaveClass("decoration-info");
    expect(getPill("Task 2")).not.toHaveClass("decoration-info");
});

test("decoration attribute with date", async () => {
    mockDate("2018-12-19T12:00:00");
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" decoration-danger="start &lt; today"/>`,
    });
    expect(getPill("Task 1")).toHaveClass("decoration-danger");
    expect(getPill("Task 2")).toHaveClass("decoration-danger");
    expect(getPill("Task 5")).toHaveClass("decoration-danger");
    expect(getPill("Task 3")).not.toHaveClass("decoration-danger");
    expect(getPill("Task 4")).not.toHaveClass("decoration-danger");
    expect(getPill("Task 7")).not.toHaveClass("decoration-danger");
});

test("consolidation feature", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                consolidation="progress"
                consolidation_max="{'user_id': 100}"
                consolidation_exclude="exclude"
                progress="progress"
            />
        `,
        groupBy: ["user_id", "project_id", "stage"],
    });

    const { rows } = getGridContent();
    expect(rows).toHaveLength(18);
    expect(rows.filter((r) => r.isGroup)).toHaveLength(12);
    expect(".o_gantt_row_headers").toHaveCount(1);

    // Check grouped rows
    expect(rows[0].isGroup).toBe(true);
    expect(rows[0].title).toBe("User 1");
    expect(rows[9].isGroup).toBe(true);
    expect(rows[9].title).toBe("User 2");

    // Consolidation
    // 0 over the size of Task 5 (Task 5 is 100 but is excluded!) then 0 over the rest of Task 1, cut by Task 4 which has progress 0
    expect(rows[0].pills).toEqual([
        { colSpan: "01 December 2018 -> 04 (1/2) December 2018", title: "0" },
        { colSpan: "04 (1/2) December 2018 -> 19 December 2018", title: "0" },
        { colSpan: "20 December 2018 -> 20 (1/2) December 2018", title: "0" },
        { colSpan: "20 (1/2) December 2018 -> Out of bounds (63) ", title: "0" },
    ]);

    // 30 over Task 2 until Task 7 then 110 (Task 2 (30) + Task 7 (80)) then 30 again until end of task 2 then 60 over Task 3
    expect(rows[9].pills).toEqual([
        { colSpan: "17 (1/2) December 2018 -> 20 (1/2) December 2018", title: "30" },
        { colSpan: "20 (1/2) December 2018 -> 20 December 2018", title: "110" },
        { colSpan: "21 December 2018 -> 22 (1/2) December 2018", title: "30" },
        { colSpan: "27 December 2018 -> Out of bounds (68) ", title: "60" },
    ]);

    const withStatus = [];
    for (const el of queryAll(".o_gantt_consolidated_pill")) {
        if (el.classList.contains("bg-success") || el.classList.contains("bg-danger")) {
            withStatus.push({
                title: el.title,
                danger: el.classList.contains("border-danger"),
            });
        }
    }

    expect(withStatus).toEqual([
        { title: "0", danger: false },
        { title: "0", danger: false },
        { title: "0", danger: false },
        { title: "0", danger: false },
        { title: "30", danger: false },
        { title: "110", danger: true },
        { title: "30", danger: false },
        { title: "60", danger: false },
    ]);
});

test("consolidation feature (single level)", async () => {
    Tasks._views.form = `
        <form>
            <field name="name"/>
            <field name="start"/>
            <field name="stop"/>
            <field name="project_id"/>
        </form>
    `;
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" consolidation="progress" consolidation_max="{'user_id': 100}" consolidation_exclude="exclude"/>`,
        groupBy: ["user_id"],
    });

    const { rows, range } = getGridContent();
    expect(range).toBe("From: 12/01/2018 to: 02/28/2019");
    expect(SELECTORS.expandButton).toHaveCount(0);
    expect(SELECTORS.collapseButton).toHaveCount(1);
    expect(rows).toEqual([
        {
            isGroup: true,
            pills: [
                { colSpan: "01 December 2018 -> 04 (1/2) December 2018", title: "0" },
                {
                    colSpan: "04 (1/2) December 2018 -> 19 December 2018",
                    title: "0",
                },
                {
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    title: "0",
                },
                {
                    colSpan: "20 (1/2) December 2018 -> Out of bounds (63) ",
                    title: "0",
                },
            ],
            title: "User 1",
        },
        {
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 (1/2) December 2018",
                    level: 0,
                    title: "Task 5",
                },
                {
                    colSpan: "01 December 2018 -> Out of bounds (63) ",
                    level: 1,
                    title: "Task 1",
                },
                {
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 0,
                    title: "Task 4",
                },
            ],
            title: "",
        },
        {
            isGroup: true,
            pills: [
                {
                    colSpan: "17 (1/2) December 2018 -> 20 (1/2) December 2018",
                    title: "30",
                },
                {
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    title: "110",
                },
                {
                    colSpan: "21 December 2018 -> 22 (1/2) December 2018",
                    title: "30",
                },
                {
                    colSpan: "27 December 2018 -> Out of bounds (68) ",
                    title: "60",
                },
            ],
            title: "User 2",
        },
        {
            pills: [
                {
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                    title: "Task 2",
                },
                {
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 1,
                    title: "Task 7",
                },
                {
                    colSpan: "27 December 2018 -> Out of bounds (68) ",
                    level: 0,
                    title: "Task 3",
                },
            ],
            title: "",
        },
    ]);
});

test("color attribute", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" color="color"/>`,
    });
    expect(getPill("Task 1")).toHaveClass("o_gantt_color_0");
    expect(getPill("Task 2")).toHaveClass("o_gantt_color_2");
});

test("color attribute in multi-level grouped", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" color="color"/>`,
        groupBy: ["user_id", "project_id"],
        domain: [["id", "=", 1]],
    });
    expect(`${SELECTORS.pill}.o_gantt_consolidated_pill`).not.toHaveClass("o_gantt_color_0");
    expect(`${SELECTORS.pill}:not(.o_gantt_consolidated_pill)`).toHaveClass("o_gantt_color_0");
});

test("color attribute on a many2one", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" color="project_id"/>`,
    });
    expect(getPill("Task 1")).toHaveClass("o_gantt_color_1");
    expect(`${SELECTORS.pill}.o_gantt_color_1`).toHaveCount(4);
    expect(`${SELECTORS.pill}.o_gantt_color_2`).toHaveCount(2);
});

test(`Today style with unavailabilities ("week": "day:half")`, async () => {
    const unavailabilities = [
        {
            start: "2018-12-18 10:00:00",
            stop: "2018-12-20 14:00:00",
        },
    ];

    onRpc("get_gantt_data", ({ parent }) => {
        const result = parent();
        result.unavailabilities.__default = { false: unavailabilities };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="week" scales="week" precision="{'week': 'day:half'}"/>`,
    });

    // Normal day / unavailability
    expect(getCellColorProperties("Tuesday 18", "Week 51, Dec 16 - Dec 22")).toEqual([
        "--Gantt__Day-background-color",
        "--Gantt__DayOff-background-color",
    ]);

    // Full unavailability
    expect(getCellColorProperties("Wednesday 19", "Week 51, Dec 16 - Dec 22")).toEqual([
        "--Gantt__DayOff-background-color",
    ]);

    // Unavailability / today
    expect(getCell("Thursday 20", "Week 51, Dec 16 - Dec 22")).toHaveClass("o_gantt_today");
    expect(getCellColorProperties("Thursday 20", "Week 51, Dec 16 - Dec 22")).toEqual([
        "--Gantt__DayOff-background-color",
        "--Gantt__DayOffToday-background-color",
    ]);
});

test("Today style of group rows", async () => {
    const unavailabilities = [
        {
            start: "2018-12-18 10:00:00",
            stop: "2018-12-20 14:00:00",
        },
    ];
    Tasks._records = [Tasks._records[3]]; // id: 4

    onRpc("get_gantt_data", ({ parent }) => {
        expect.step("get_gantt_data");
        const result = parent();
        result.unavailabilities.project_id = { 1: unavailabilities };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="week" scales="week" precision="{'week': 'day:half'}"/>`,
        groupBy: ["user_id", "project_id"],
    });
    expect.verifySteps(["get_gantt_data"]);
    await contains(".o_gantt_header_folded").click();

    // Normal group cell: open
    let cell4 = getCell("Wednesday 19", "Week 51, Dec 16 - Dec 22");
    expect(cell4).not.toHaveClass("o_gantt_today");
    expect(cell4).toHaveClass("o_group_open");
    expect(cell4).toHaveStyle({
        backgroundImage: "linear-gradient(rgb(249, 250, 251), rgb(234, 237, 241))",
    });

    // Today group cell: open
    let cell5 = getCell("Thursday 20", "Week 51, Dec 16 - Dec 22");
    expect(cell5).toHaveClass("o_gantt_today");
    expect(cell5).toHaveClass("o_group_open");
    expect(cell5).toHaveStyle({
        backgroundImage: "linear-gradient(rgb(249, 250, 251), rgb(234, 237, 241))",
    });
    await contains(SELECTORS.group).click(); // fold group
    await leave();
    // Normal group cell: closed
    cell4 = getCell("Wednesday 19", "Week 51, Dec 16 - Dec 22");
    expect(cell4).not.toHaveClass("o_gantt_today");
    expect(cell4).not.toHaveClass("o_group_open");
    expect(cell4).toHaveStyle({
        backgroundImage: "linear-gradient(rgb(234, 237, 241), rgb(249, 250, 251))",
    });

    // Today group cell: closed
    cell5 = getCell("Thursday 20", "Week 51, Dec 16 - Dec 22");
    expect(cell5).toHaveClass("o_gantt_today");
    expect(cell5).not.toHaveClass("o_group_open");
    expect(cell5).toHaveStyle({ backgroundImage: "none" });
    expect(cell5).toHaveStyle({ backgroundColor: "rgb(252, 250, 243)" });
});

test("style without unavailabilities", async () => {
    mockDate("2018-12-05T02:00:00");

    onRpc("get_gantt_data", ({ kwargs }) => {
        expect.step("get_gantt_data");
        expect(kwargs.unavailability_fields).toEqual([]);
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1"/>`,
    });
    expect.verifySteps(["get_gantt_data"]);
    const cell5 = getCell("05", "December 2018");
    expect(cell5).toHaveClass("o_gantt_today");
    expect(cell5).toHaveAttribute("style", "grid-column:c9/c11;grid-row:r1/r5;");
    const cell6 = getCell("06", "December 2018");
    expect(cell6).toHaveAttribute("style", "grid-column:c11/c13;grid-row:r1/r5;");
});

test(`Unavailabilities ("month": "day:half")`, async () => {
    mockDate("2018-12-05T02:00:00");

    const unavailabilities = [
        {
            start: "2018-12-05 09:30:00",
            stop: "2018-12-07 08:00:00",
        },
        {
            start: "2018-12-16 09:00:00",
            stop: "2018-12-18 13:00:00",
        },
    ];
    onRpc("get_gantt_data", ({ model, kwargs, parent }) => {
        expect.step("get_gantt_data");
        expect(model).toBe("tasks");
        expect(kwargs.unavailability_fields).toEqual([]);
        expect(kwargs.start_date).toBe("2018-11-30 23:00:00");
        expect(kwargs.stop_date).toBe("2019-02-28 23:00:00");
        const result = parent();
        result.unavailabilities = { __default: { false: unavailabilities } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1"/>`,
    });
    expect.verifySteps(["get_gantt_data"]);
    expect(getCell("05", "December 2018")).toHaveClass("o_gantt_today");
    expect(getCellColorProperties("05", "December 2018")).toEqual([
        "--Gantt__DayOffToday-background-color",
        "--Gantt__DayOff-background-color",
    ]);
    expect(getCellColorProperties("06", "December 2018")).toEqual([
        "--Gantt__DayOff-background-color",
    ]);
    expect(getCellColorProperties("07", "December 2018")).toEqual([]);
    expect(getCellColorProperties("16", "December 2018")).toEqual([
        "--Gantt__Day-background-color",
        "--Gantt__DayOff-background-color",
    ]);
    expect(getCellColorProperties("17", "December 2018")).toEqual([
        "--Gantt__DayOff-background-color",
    ]);
    expect(getCellColorProperties("18", "December 2018")).toEqual([
        "--Gantt__DayOff-background-color",
        "--Gantt__Day-background-color",
    ]);
});

test(`Unavailabilities ("day": "hours:quarter")`, async () => {
    Tasks._records = [];
    const unavailabilities = [
        // in utc
        {
            start: "2018-12-19 08:15:00",
            stop: "2018-12-19 08:30:00",
        },
        {
            start: "2018-12-19 10:35:00",
            stop: "2018-12-19 12:29:00",
        },
        {
            start: "2018-12-19 20:15:00",
            stop: "2018-12-19 20:50:00",
        },
    ];
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        expect(kwargs.unavailability_fields).toEqual([]);
        const result = parent();
        result.unavailabilities = { __default: { false: unavailabilities } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="day" precision="{'day': 'hours:quarter'}"/>`,
    });
    await contains(".o_content").scroll({ left: 0 });
    expect(getCellColorProperties("9am", "December 19, 2018")).toEqual([
        "--Gantt__Day-background-color",
        "--Gantt__DayOff-background-color",
        "--Gantt__DayOff-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
    ]);
    expect(getCellColorProperties("11am", "December 19, 2018")).toEqual([
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__DayOff-background-color",
    ]);
    expect(getCellColorProperties("12pm", "December 19, 2018")).toEqual([
        "--Gantt__DayOff-background-color",
    ]);
    expect(getCellColorProperties("1pm", "December 19, 2018")).toEqual([
        "--Gantt__DayOff-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
    ]);
    expect(getCellColorProperties("9pm", "December 19, 2018")).toEqual([
        "--Gantt__Day-background-color",
        "--Gantt__DayOff-background-color",
        "--Gantt__DayOff-background-color",
        "--Gantt__DayOff-background-color",
        "--Gantt__DayOff-background-color",
        "--Gantt__Day-background-color",
    ]);
});

test(`Fold unavailabilities ("day": "hours:quarter")`, async () => {
    Tasks._records = [Tasks._records[3]]; // id: 4
    const unavailabilities = [
        // in utc
        {
            start: "2018-12-18 16:00:00",
            stop: "2018-12-19 07:00:00",
        },
        {
            start: "2018-12-19 11:00:00",
            stop: "2018-12-19 12:25:00",
        },
        {
            start: "2018-12-19 16:15:00",
            stop: "2018-12-20 08:00:00",
        },
        {
            start: "2018-12-20 16:15:00",
            stop: "2018-12-22 08:00:00",
        },
    ];
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        expect(kwargs.unavailability_fields).toEqual([]);
        const result = parent();
        result.unavailabilities = { __default: { false: unavailabilities } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" scales="day" default_range="day" precision="{'day': 'hours:quarter'}"/>`,
    });
    await contains(".o_content").scroll({ left: 0 });
    const { columnHeaders, groupHeaders } = getGridContent({ setTitleAttrOnHeaders: true });
    expect(columnHeaders).toHaveLength(28);
    expect(groupHeaders).toEqual(
        [
            {
                range: [1, 97],
                title: "December 19, 2018",
                titleAttr: "Wednesday, December 19, 2018",
            },
            {
                range: [97, 193],
                title: "December 20, 2018",
                titleAttr: "Thursday, December 20, 2018",
            },
            {
                range: [193, 289],
                title: "",
                titleAttr: "",
            },
        ],
        { message: "Last group's title is hidden since all of its content is folded" }
    );
    expect(columnHeaders).toEqual([
        { range: [1, 33], title: "", titleAttr: "" },
        { range: [33, 37], title: "8am", titleAttr: "Wednesday, December 19, 2018, 8:00 AM" },
        { range: [37, 41], title: "9am", titleAttr: "Wednesday, December 19, 2018, 9:00 AM" },
        { range: [41, 45], title: "10am", titleAttr: "Wednesday, December 19, 2018, 10:00 AM" },
        { range: [45, 49], title: "11am", titleAttr: "Wednesday, December 19, 2018, 11:00 AM" },
        { range: [49, 53], title: "12pm", titleAttr: "Wednesday, December 19, 2018, 12:00 PM" },
        { range: [53, 57], title: "1pm", titleAttr: "Wednesday, December 19, 2018, 1:00 PM" },
        { range: [57, 61], title: "2pm", titleAttr: "Wednesday, December 19, 2018, 2:00 PM" },
        { range: [61, 65], title: "3pm", titleAttr: "Wednesday, December 19, 2018, 3:00 PM" },
        { range: [65, 69], title: "4pm", titleAttr: "Wednesday, December 19, 2018, 4:00 PM" },
        { range: [69, 73], title: "5pm", titleAttr: "Wednesday, December 19, 2018, 5:00 PM" },
        { range: [73, 109], title: "", titleAttr: "" },
        { range: [109, 113], title: "3am", titleAttr: "Thursday, December 20, 2018, 3:00 AM" },
        { range: [113, 117], title: "4am", titleAttr: "Thursday, December 20, 2018, 4:00 AM" },
        { range: [117, 121], title: "5am", titleAttr: "Thursday, December 20, 2018, 5:00 AM" },
        { range: [121, 125], title: "6am", titleAttr: "Thursday, December 20, 2018, 6:00 AM" },
        { range: [125, 129], title: "7am", titleAttr: "Thursday, December 20, 2018, 7:00 AM" },
        { range: [129, 133], title: "8am", titleAttr: "Thursday, December 20, 2018, 8:00 AM" },
        { range: [133, 137], title: "9am", titleAttr: "Thursday, December 20, 2018, 9:00 AM" },
        { range: [137, 141], title: "10am", titleAttr: "Thursday, December 20, 2018, 10:00 AM" },
        { range: [141, 145], title: "11am", titleAttr: "Thursday, December 20, 2018, 11:00 AM" },
        { range: [145, 149], title: "12pm", titleAttr: "Thursday, December 20, 2018, 12:00 PM" },
        { range: [149, 153], title: "1pm", titleAttr: "Thursday, December 20, 2018, 1:00 PM" },
        { range: [153, 157], title: "2pm", titleAttr: "Thursday, December 20, 2018, 2:00 PM" },
        { range: [157, 161], title: "3pm", titleAttr: "Thursday, December 20, 2018, 3:00 PM" },
        { range: [161, 165], title: "4pm", titleAttr: "Thursday, December 20, 2018, 4:00 PM" },
        { range: [165, 169], title: "5pm", titleAttr: "Thursday, December 20, 2018, 5:00 PM" },
        { range: [169, 289], title: "", titleAttr: "" },
    ]);
    expect(".o_gantt_header_cell .fa-caret-left:visible").toHaveCount(3);
    expect(queryFirst(".o_gantt_cell").offsetWidth).toBe(36, {
        message: "Folded cells have a fixed width of 36px",
    });
});

test(`Fold unavailabilities ("week": "day:half")`, async () => {
    Tasks._records = [Tasks._records[3]]; // id: 4
    const unavailabilities = [
        // in utc
        {
            start: "2018-12-14 16:00:00",
            stop: "2018-12-17 07:00:00",
        },
        {
            start: "2018-12-18 16:15:00",
            stop: "2018-12-20 08:00:00",
        },
    ];
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        expect(kwargs.unavailability_fields).toEqual([]);
        const result = parent();
        result.unavailabilities = { __default: { false: unavailabilities } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="week" scales="week" precision="{'week': 'day:half'}"/>`,
    });
    const { columnHeaders, groupHeaders } = getGridContent({ setTitleAttrOnHeaders: true });
    expect(columnHeaders).toHaveLength(11);
    expect(groupHeaders).toEqual([
        {
            range: [1, 15],
            title: "Week 50, Dec 9 - Dec 15",
            titleAttr: "Week 50, Dec 9 - Dec 15",
        },
        {
            range: [15, 29],
            title: "Week 51, Dec 16 - Dec 22",
            titleAttr: "Week 51, Dec 16 - Dec 22",
        },
        {
            range: [29, 43],
            title: "Week 52, Dec 23 - Dec 29",
            titleAttr: "Week 52, Dec 23 - Dec 29",
        },
    ]);
    expect(columnHeaders).toEqual([
        { range: [11, 13], title: "Friday 14", titleAttr: "Friday, December 14, 2018" },
        { range: [13, 17], title: "", titleAttr: "" },
        { range: [17, 19], title: "Monday 17", titleAttr: "Monday, December 17, 2018" },
        { range: [19, 21], title: "Tuesday 18", titleAttr: "Tuesday, December 18, 2018" },
        { range: [21, 23], title: "", titleAttr: "" }, // Single unavailability columns are folded in week scale
        { range: [23, 25], title: "Thursday 20", titleAttr: "Thursday, December 20, 2018" },
        { range: [25, 27], title: "Friday 21", titleAttr: "Friday, December 21, 2018" },
        { range: [27, 29], title: "Saturday 22", titleAttr: "Saturday, December 22, 2018" },
        { range: [29, 31], title: "Sunday 23", titleAttr: "Sunday, December 23, 2018" },
        { range: [31, 33], title: "Monday 24", titleAttr: "Monday, December 24, 2018" },
        { range: [33, 35], title: "Tuesday 25", titleAttr: "Tuesday, December 25, 2018" },
    ]);
    expect(".o_gantt_header_cell .fa-caret-left:visible").toHaveCount(2);
});

test(`Fold unavailabilities ("month": "day:half")`, async () => {
    Tasks._records = [Tasks._records[3]]; // id: 4
    const unavailabilities = [
        // in utc
        {
            start: "2018-11-13 16:00:00",
            stop: "2018-11-16 07:00:00",
        },
        {
            start: "2018-11-19 16:15:00",
            stop: "2018-11-29 08:00:00",
        },
    ];
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        expect(kwargs.unavailability_fields).toEqual([]);
        const result = parent();
        result.unavailabilities = { __default: { false: unavailabilities } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="month" scales="month" precision="{'month': 'day:half'}"/>`,
    });
    await contains(".o_content").scroll({ left: 0 });
    const { columnHeaders, groupHeaders } = getGridContent({ setTitleAttrOnHeaders: true });
    expect(columnHeaders).toHaveLength(30);
    expect(groupHeaders).toEqual([
        {
            range: [1, 61],
            title: "November 2018",
            titleAttr: "November 2018",
        },
        {
            range: [61, 123],
            title: "December 2018",
            titleAttr: "December 2018",
        },
    ]);
    expect(columnHeaders).toEqual([
        { range: [1, 3], title: "01", titleAttr: "Thursday, November 1, 2018" },
        { range: [3, 5], title: "02", titleAttr: "Friday, November 2, 2018" },
        { range: [5, 7], title: "03", titleAttr: "Saturday, November 3, 2018" },
        { range: [7, 9], title: "04", titleAttr: "Sunday, November 4, 2018" },
        { range: [9, 11], title: "05", titleAttr: "Monday, November 5, 2018" },
        { range: [11, 13], title: "06", titleAttr: "Tuesday, November 6, 2018" },
        { range: [13, 15], title: "07", titleAttr: "Wednesday, November 7, 2018" },
        { range: [15, 17], title: "08", titleAttr: "Thursday, November 8, 2018" },
        { range: [17, 19], title: "09", titleAttr: "Friday, November 9, 2018" },
        { range: [19, 21], title: "10", titleAttr: "Saturday, November 10, 2018" },
        { range: [21, 23], title: "11", titleAttr: "Sunday, November 11, 2018" },
        { range: [23, 25], title: "12", titleAttr: "Monday, November 12, 2018" },
        { range: [25, 27], title: "13", titleAttr: "Tuesday, November 13, 2018" },
        { range: [27, 31], title: "", titleAttr: "" },
        { range: [31, 33], title: "16", titleAttr: "Friday, November 16, 2018" },
        { range: [33, 35], title: "17", titleAttr: "Saturday, November 17, 2018" },
        { range: [35, 37], title: "18", titleAttr: "Sunday, November 18, 2018" },
        { range: [37, 39], title: "19", titleAttr: "Monday, November 19, 2018" },
        { range: [39, 57], title: "", titleAttr: "" },
        { range: [57, 59], title: "29", titleAttr: "Thursday, November 29, 2018" },
        { range: [59, 61], title: "30", titleAttr: "Friday, November 30, 2018" },
        { range: [61, 63], title: "01", titleAttr: "Saturday, December 1, 2018" },
        { range: [63, 65], title: "02", titleAttr: "Sunday, December 2, 2018" },
        { range: [65, 67], title: "03", titleAttr: "Monday, December 3, 2018" },
        { range: [67, 69], title: "04", titleAttr: "Tuesday, December 4, 2018" },
        { range: [69, 71], title: "05", titleAttr: "Wednesday, December 5, 2018" },
        { range: [71, 73], title: "06", titleAttr: "Thursday, December 6, 2018" },
        { range: [73, 75], title: "07", titleAttr: "Friday, December 7, 2018" },
        { range: [75, 77], title: "08", titleAttr: "Saturday, December 8, 2018" },
        { range: [77, 79], title: "09", titleAttr: "Sunday, December 9, 2018" },
    ]);
    expect(".o_gantt_header_cell .fa-caret-left:visible").toHaveCount(2);
    const cell1 = queryFirst(".o_gantt_cell");
    const cell2 = queryOne(".o_gantt_cell:eq(1)");
    expect(Math.abs(cell1.clientWidth - cell2.clientWidth)).toBeLessThan(4, {
        message:
            "Folded cells have similar width compared to regular cells besides covering a wider date range",
    });
});

test(`Fold unavailabilities with multiple rows`, async () => {
    const unavailabilities1 = [
        // in utc
        { start: "2018-12-18 16:00:00", stop: "2018-12-19 07:00:00" },
        { start: "2018-12-19 11:00:00", stop: "2018-12-19 12:25:00" },
        { start: "2018-12-19 16:15:00", stop: "2018-12-20 08:00:00" },
        { start: "2018-12-20 16:15:00", stop: "2018-12-22 08:00:00" },
    ];
    const unavailabilities2 = [
        // in utc
        { start: "2018-12-18 16:00:00", stop: "2018-12-19 09:00:00" },
        { start: "2018-12-19 13:15:00", stop: "2018-12-20 08:00:00" },
        { start: "2018-12-20 20:15:00", stop: "2018-12-22 08:00:00" },
    ];
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        expect(kwargs.unavailability_fields).toEqual(["user_id"]);
        const result = parent();
        result.unavailabilities = { user_id: { 1: unavailabilities1, 2: unavailabilities2 } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="day" scales="day" precision="{'day': 'hours:quarter'}"/>`,
        groupBy: ["user_id"],
        domain: [["id", "in", [4, 7]]],
    });
    const { columnHeaders, groupHeaders } = getGridContent();
    expect(groupHeaders).toEqual([
        { range: [1, 97], title: "December 19, 2018" },
        { range: [97, 193], title: "December 20, 2018" },
        { range: [193, 289], title: "" },
    ]);
    expect(columnHeaders).toEqual([
        { range: [1, 33], title: "" },
        { range: [33, 37], title: "8am" },
        { range: [37, 41], title: "9am" },
        { range: [41, 45], title: "10am" },
        { range: [45, 49], title: "11am" },
        { range: [49, 53], title: "12pm" },
        { range: [53, 57], title: "1pm" },
        { range: [57, 61], title: "2pm" },
        { range: [61, 65], title: "3pm" },
        { range: [65, 69], title: "4pm" },
        { range: [69, 73], title: "5pm" },
        { range: [73, 109], title: "" },
        { range: [109, 113], title: "3am" },
        { range: [113, 117], title: "4am" },
        { range: [117, 121], title: "5am" },
        { range: [121, 125], title: "6am" },
        { range: [125, 129], title: "7am" },
        { range: [129, 133], title: "8am" },
        { range: [133, 137], title: "9am" },
        { range: [137, 141], title: "10am" },
        { range: [141, 145], title: "11am" },
        { range: [145, 149], title: "12pm" },
        { range: [149, 153], title: "1pm" },
        { range: [153, 157], title: "2pm" },
        { range: [157, 161], title: "3pm" },
        { range: [161, 165], title: "4pm" },
        { range: [165, 169], title: "5pm" },
        { range: [169, 173], title: "6pm" },
        { range: [173, 177], title: "7pm" },
        { range: [177, 181], title: "8pm" },
        { range: [181, 185], title: "9pm" },
        { range: [185, 289], title: "" },
    ]);
});

test(`Partial fold/unfold in gantt`, async () => {
    Tasks._records = [Tasks._records[3]]; // id: 4
    const unavailabilities = [
        // in utc
        {
            start: "2018-12-18 16:00:00",
            stop: "2018-12-19 07:00:00",
        },
        {
            start: "2018-12-19 11:00:00",
            stop: "2018-12-19 12:25:00",
        },
        {
            start: "2018-12-19 16:15:00",
            stop: "2018-12-20 08:00:00",
        },
        {
            start: "2018-12-20 16:15:00",
            stop: "2018-12-22 08:00:00",
        },
    ];
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        expect(kwargs.unavailability_fields).toEqual([]);
        const result = parent();
        result.unavailabilities = { __default: { false: unavailabilities } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="day" scales="day" precision="{'day': 'hours:quarter'}"/>`,
    });
    setCellParts(4);
    await contains(".o_content").scroll({ left: 0 });
    let { columnHeaders, rows } = getGridContent();
    expect(columnHeaders).toHaveLength(28);
    expect(columnHeaders[11]).toEqual({
        range: [73, 109],
        title: "",
    });
    expect(rows[0].pills[0]).toEqual({
        title: "Task 4",
        colSpan: "3am (2/4) December 20, 2018 -> 7am (2/4) December 20, 2018",
        level: 0,
    });
    await contains(".o_gantt_cell:eq(11)").click();
    ({ columnHeaders } = getGridContent());
    expect(columnHeaders).toHaveLength(36);
    expect(columnHeaders[11]).toEqual({
        range: [73, 77],
        title: "6pm",
    });
    await runAllTimers();
    await contains(".o_gantt_cell:eq(0)").click();
    ({ columnHeaders } = getGridContent());
    expect(columnHeaders).toHaveLength(38);
    expect(columnHeaders[11]).toEqual({
        range: [45, 49],
        title: "11am",
    });
    expect(columnHeaders[18]).toEqual({
        range: [73, 77],
        title: "6pm",
    });
    await contains(".o_gantt_header_cell:eq(18)").hover();
    expect(".o_gantt_header_cell:eq(19)").toHaveClass("o_gantt_foldable_hovered");
    await contains(".o_gantt_header_cell:eq(18)").click();
    ({ columnHeaders } = getGridContent());
    expect(columnHeaders).toHaveLength(35);
    expect(columnHeaders[18]).toEqual({
        range: [73, 109],
        title: "",
    });
    const { drop } = await dragPill("Task 4");
    await drop({ columnHeader: "5pm", groupHeader: "December 19, 2018", part: 4 });
    ({ columnHeaders, rows } = getGridContent());
    expect(columnHeaders).toHaveLength(39);
    expect(columnHeaders[18]).toEqual({
        range: [73, 77],
        title: "6pm",
    });
    expect(columnHeaders[22]).toEqual({
        range: [89, 109],
        title: "",
    });
    expect(rows[0].pills[0]).toEqual({
        title: "Task 4",
        colSpan: "5pm (3/4) December 19, 2018 -> 9pm (3/4) December 19, 2018",
        level: 0,
    });
    await resizePill(getPillWrapper("Task 4"), "end", +1); // wrong but we don't want to rewrite helpers for this
    ({ columnHeaders, rows } = getGridContent());
    expect(columnHeaders).toHaveLength(39);
    expect(columnHeaders[22]).toEqual({
        range: [89, 93],
        title: "10pm",
    });
    expect(rows[0].pills[0]).toEqual({
        title: "Task 4",
        colSpan: "5pm (3/4) December 19, 2018 -> 3am December 20, 2018",
        level: 0,
    });
});

test(`Full unavailabilities period`, async () => {
    Tasks._records = []; // no pill
    const unavailabilities = [
        // in utc
        {
            start: "2018-12-18 16:00:00",
            stop: "2018-12-23 07:00:00",
        },
    ];
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        expect(kwargs.unavailability_fields).toEqual([]);
        const result = parent();
        result.unavailabilities = { __default: { false: unavailabilities } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="day" scales="day" precision="{'day': 'hours:quarter'}"/>`,
    });
    // Only one folded cell appears which takes the full screen width instead of 36px
    expect(SELECTORS.cell).toHaveCount(1);
    expect(SELECTORS.cell).toHaveClass("o_gantt_cell_folded");
    expect(SELECTORS.cell).toHaveRect({ width: 1366 });
    expect(SELECTORS.groupHeader).toHaveCount(2);
    expect(queryAllTexts(SELECTORS.groupHeader)).toEqual(["", ""]);

    await contains(SELECTORS.cell).click();
    const { columnHeaders, groupHeaders } = getGridContent();
    expect(groupHeaders).toEqual([
        { range: [1, 97], title: "December 19, 2018" },
        { range: [97, 193], title: "December 20, 2018" },
    ]);
    expect(columnHeaders).toEqual([
        { range: [1, 5], title: "12am" },
        { range: [5, 9], title: "1am" },
        { range: [9, 13], title: "2am" },
        { range: [13, 17], title: "3am" },
        { range: [17, 21], title: "4am" },
        { range: [21, 25], title: "5am" },
        { range: [25, 29], title: "6am" },
        { range: [29, 33], title: "7am" },
        { range: [33, 37], title: "8am" },
        { range: [37, 41], title: "9am" },
        { range: [41, 45], title: "10am" },
        { range: [45, 49], title: "11am" },
        { range: [49, 53], title: "12pm" },
        { range: [53, 57], title: "1pm" },
        { range: [57, 61], title: "2pm" },
        { range: [61, 65], title: "3pm" },
        { range: [65, 69], title: "4pm" },
        { range: [69, 73], title: "5pm" },
        { range: [73, 77], title: "6pm" },
        { range: [77, 81], title: "7pm" },
        { range: [81, 85], title: "8pm" },
        { range: [85, 89], title: "9pm" },
        { range: [89, 93], title: "10pm" },
        { range: [93, 97], title: "11pm" },
        { range: [97, 101], title: "12am" },
        { range: [101, 105], title: "1am" },
        { range: [105, 109], title: "2am" },
        { range: [109, 113], title: "3am" },
        { range: [113, 117], title: "4am" },
        { range: [117, 121], title: "5am" },
        { range: [121, 125], title: "6am" },
        { range: [125, 129], title: "7am" },
        { range: [129, 133], title: "8am" },
        { range: [133, 137], title: "9am" },
        { range: [137, 141], title: "10am" },
        { range: [141, 145], title: "11am" },
        { range: [145, 149], title: "12pm" },
        { range: [149, 153], title: "1pm" },
    ]);
});

test("default_group_by attribute", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" default_group_by="user_id"/>`,
    });

    expect(`.o_searchview_facet`).toHaveCount(1);
    expect(`.o_searchview_facet`).toHaveText("Assign To");
    const { rows } = getGridContent();
    expect(rows).toEqual([
        {
            title: "User 1",
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 (1/2) December 2018",
                    level: 0,
                    title: "Task 5",
                },
                {
                    colSpan: "01 December 2018 -> Out of bounds (63) ",
                    level: 1,
                    title: "Task 1",
                },
                {
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 0,
                    title: "Task 4",
                },
            ],
        },
        {
            title: "User 2",
            pills: [
                {
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                    title: "Task 2",
                },
                {
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 1,
                    title: "Task 7",
                },
                {
                    colSpan: "27 December 2018 -> Out of bounds (68) ",
                    level: 0,
                    title: "Task 3",
                },
            ],
        },
    ]);
});

test("default_group_by attribute with groupBy", async () => {
    // The default_group_by attribute should be ignored if a groupBy is given.
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" default_group_by="user_id"/>`,
        groupBy: ["project_id"],
    });

    expect(`.o_searchview_facet`).toHaveCount(0);
    const { rows } = getGridContent();
    expect(rows).toEqual([
        {
            title: "Project 1",
            pills: [
                {
                    colSpan: "01 December 2018 -> Out of bounds (63) ",
                    level: 0,
                    title: "Task 1",
                },
                {
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 1,
                    title: "Task 2",
                },
                {
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 2,
                    title: "Task 4",
                },
                {
                    colSpan: "27 December 2018 -> Out of bounds (68) ",
                    level: 1,
                    title: "Task 3",
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
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 0,
                    title: "Task 7",
                },
            ],
        },
    ]);
});

test("default_group_by attribute with 2 fields", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" default_group_by="user_id,project_id"/>`,
    });

    expect(`.o_searchview_facet`).toHaveCount(1);
    expect(`.o_searchview_facet`).toHaveText("Assign To\n>\nProject");
    const { rows } = getGridContent();
    expect(rows).toEqual([
        {
            title: "User 1",
            isGroup: true,
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 (1/2) December 2018",
                    title: "2",
                },
                {
                    colSpan: "04 (1/2) December 2018 -> 19 December 2018",
                    title: "1",
                },
                {
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    title: "2",
                },
                {
                    colSpan: "20 (1/2) December 2018 -> Out of bounds (63) ",
                    title: "1",
                },
            ],
        },
        {
            title: "Project 1",
            pills: [
                {
                    colSpan: "01 December 2018 -> Out of bounds (63) ",
                    level: 0,
                    title: "Task 1",
                },
                {
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 1,
                    title: "Task 4",
                },
            ],
        },
        {
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 (1/2) December 2018",
                    level: 0,
                    title: "Task 5",
                },
            ],
            title: "Project 2",
        },
        {
            title: "User 2",
            isGroup: true,
            pills: [
                {
                    colSpan: "17 (1/2) December 2018 -> 20 (1/2) December 2018",
                    title: "1",
                },
                {
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    title: "2",
                },
                {
                    colSpan: "21 December 2018 -> 22 (1/2) December 2018",
                    title: "1",
                },
                {
                    colSpan: "27 December 2018 -> Out of bounds (68) ",
                    title: "1",
                },
            ],
        },
        {
            title: "Project 1",
            pills: [
                {
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                    title: "Task 2",
                },
                {
                    colSpan: "27 December 2018 -> Out of bounds (68) ",
                    level: 0,
                    title: "Task 3",
                },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 0,
                    title: "Task 7",
                },
            ],
        },
    ]);
});

test("default_range attribute", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" default_range="day"/>`,
    });
    const { columnHeaders, range } = getGridContent();
    expect(range).toBe("Day");
    expect(columnHeaders).toHaveLength(42);
    await click(SELECTORS.scaleSelectorToggler);
    await animationFrame();
    const firstRangeMenuItem = queryFirst(`${SELECTORS.scaleSelectorMenu} .dropdown-item`);
    expect(firstRangeMenuItem).toHaveClass("active");
    expect(firstRangeMenuItem).toHaveText("Day");
});

test("consolidation and unavailabilities", async () => {
    const unavailabilities = [
        {
            start: "2018-12-18 10:00:00",
            stop: "2018-12-20 14:00:00",
        },
    ];
    onRpc("get_gantt_data", ({ parent, kwargs }) => {
        expect.step("get_gantt_data");
        const result = parent();
        expect(kwargs.unavailability_fields).toEqual(["user_id"]);
        result.unavailabilities.user_id = { 1: unavailabilities };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                consolidation="progress"
                consolidation_max="{'user_id': 100}"
                consolidation_exclude="exclude"
                display_unavailability="1"
            />
        `,
        groupBy: ["user_id"],
    });
    expect.verifySteps(["get_gantt_data"]);
    // Normal day / unavailability
    expect(getCellColorProperties("18", "December 2018", "", { num: 2 })).toEqual([
        "--Gantt__Day-background-color",
        "--Gantt__DayOff-background-color",
    ]);

    // Full unavailability
    expect(getCellColorProperties("19", "December 2018", "", { num: 2 })).toEqual([
        "--Gantt__DayOff-background-color",
    ]);

    // Unavailability / today
    expect(getCell("20", "December 2018")).toHaveClass("o_gantt_today");
    expect(getCellColorProperties("20", "December 2018", "", { num: 2 })).toEqual([
        "--Gantt__DayOff-background-color",
        "--Gantt__DayOffToday-background-color",
    ]);
});

test("default_range not in scales", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" scales="month" default_range="year"/>`,
    });
    const { range } = getGridContent();
    expect(range).toBe("Year");

    await contains(SELECTORS.scaleSelectorToggler).click();
    await animationFrame();
    expect(`${SELECTORS.scaleSelectorMenu} .dropdown-item`).toHaveCount(3);
    expect(queryAllTexts(`${SELECTORS.scaleSelectorMenu} .dropdown-item`)).toEqual([
        "Month",
        "Year",
        "From\n01/01/2017\nto\n12/31/2019\nApply",
    ]);
});

test("kanban_view_id attribute", async () => {
    Tasks._views["kanban,42"] = `
        <kanban>
            <templates>
                <t t-name="card">
                    Allocated Hours: <field name="allocated_hours"/>
                </t>
            </templates>
        </kanban>
    `;
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" kanban_view_id="42"/>`,
    });
    expect(`.o_popover`).toHaveCount(0);
    await contains(SELECTORS.pill).click();
    expect(`.o_popover`).toHaveCount(1);
    expect(`.o_popover .popover-header`).toHaveCount(0);
    await contains(`.o_popover .popover-footer i.fa.fa-close`).click();
    expect(`.o_popover`).toHaveCount(0);
});

test("template in arch get favors vs kanban_view_id attribute", async () => {
    Tasks._views["kanban,42"] = `
        <kanban>
            <templates>
                <t t-name="card">
                    Allocated Hours: <field name="allocated_hours"/>
                </t>
            </templates>
        </kanban>
    `;
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt date_start="start" date_stop="stop" kanban_view_id="42">
                <templates>
                    <t t-name="gantt-popover">
                        <div t-esc="display_name"/>
                    </t>
                </templates>
            </gantt>
        `,
    });
    expect(`.o_popover`).toHaveCount(0);
    await contains(SELECTORS.pill).click();
    expect(`.o_popover`).toHaveCount(1);
    expect(`.o_popover .popover-body .o_kanban_record`).toHaveCount(0);
    expect(`.o_popover .popover-header`).toHaveText("Task 5");
    expect(`.o_popover .popover-body div`).toHaveText("Task 5");
    expect(`.o_popover .popover-footer i.fa.fa-close`).toHaveCount(0);
    await contains(`.o_popover .popover-header i.fa.fa-close`).click();
    expect(`.o_popover`).toHaveCount(0);
});

test("if kanban_view_id attribute is not set, kanban view id is retrieved from config", async () => {
    Tasks._views.kanban = `
        <kanban>
            <templates>
                <t t-name="card">
                    Allocated Hours: <field name="allocated_hours"/>
                </t>
            </templates>
        </kanban>
    `;
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
        config: {
            views: [
                [false, "kanban"],
                [false, "gantt"],
            ],
        },
    });
    expect(`.o_popover`).toHaveCount(0);
    await contains(SELECTORS.pill).click();
    expect(`.o_popover`).toHaveCount(1);
    expect(`.o_popover .popover-header`).toHaveCount(0);
    expect(`.o_popover .popover-body .o_kanban_record`).toHaveText("Allocated Hours:\n0.00");
    await contains(`.o_popover .popover-footer i.fa.fa-close`).click();
    expect(`.o_popover`).toHaveCount(0);
});

test("verifies context-driven text visibility in Kanban view", async () => {
    Tasks._views.kanban = `
        <kanban>
            <templates>
                <t t-name="card">
                    Allocated Hours: <field name="allocated_hours"/>
                    <div invisible="context.get('isProjectNameHidden')">Project A</div>
                    <div invisible="context.get('isTaskNameHidden')">Test 5</div>
                </t>
            </templates>
        </kanban>
    `;

    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
        config: {
            views: [
                [false, "kanban"],
                [false, "gantt"],
            ],
        },
        context: { isTaskNameHidden: true, isProjectNameHidden: false },
    });
    await contains(SELECTORS.pill).click();
    expect(`.o_popover .popover-body .o_kanban_record`).toHaveText(
        "Allocated Hours:\n0.00\nProject A"
    );
});
