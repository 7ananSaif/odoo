import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click, edit, keyDown, keyUp } from "@odoo/hoot-dom";
import { animationFrame, disableAnimations, mockDate, mockTimeZone } from "@odoo/hoot-mock";

import { contains, defineParams, onRpc } from "@web/../tests/web_test_helpers";
import { Tasks, defineGanttModels } from "./gantt_mock_models";
import {
    dragPill,
    getCell,
    getGridContent,
    hoverCell,
    mountGanttView,
} from "./web_gantt_test_helpers";

import { Domain } from "@web/core/domain";

describe.current.tags("desktop");

Tasks._views = {
    "form,multi_create_form": `
        <form>
            <group>
                <field name="name" required="1"/>
                <field name="progress"/>
            </group>
        </form>
    `,
    "form,multi_create_form_state": `
        <form>
            <group>
                <field name="name" required="1"/>
                <field name="progress"/>
                <field name="user_id"/>
            </group>
        </form>
    `,
};

defineGanttModels();
beforeEach(() => {
    mockDate("2018-12-20T08:00:00", +1);
    defineParams({
        lang_parameters: {
            time_format: "%I:%M:%S",
        },
    });
    disableAnimations();
});

beforeEach(() => {
    mockTimeZone("Europe/Brussels");
});

// Utils function

async function multiCreateClickAddButton() {
    await click(".o_multi_selection_buttons .btn:contains(Add)");
    await animationFrame();
}

async function multiCreatePopoverClickAddButton() {
    await click(".o_multi_create_popover .popover-footer .btn:contains(Add)");
    await animationFrame();
}

async function selectBlock({ sourceCell, targetCell }) {
    await hoverCell(sourceCell);
    const { drop, moveTo } = await contains(sourceCell).drag();
    await moveTo(targetCell);
    await animationFrame();
    await drop();
    await animationFrame();
}

test("multi_create: render and basic creation/deletion", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                precision="{'day':'hour:full', 'week':'day:full', 'month':'day:full'}"
                multi_create_view="multi_create_form"
            >
                <field name="progress"/>
            </gantt>
        `,
        groupBy: ["stage_id"],
    });
    let gridContent = getGridContent();
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 December 2018",
                    level: 0,
                    title: "Task 5",
                },
            ],
            title: "todo",
        },
        {
            title: "in_progress",
            pills: [
                { level: 0, colSpan: "01 December 2018 -> Out of bounds (32) ", title: "Task 1" },
                {
                    level: 1,
                    colSpan: "20 December 2018 -> 20 December 2018",
                    title: "Task 7",
                },
            ],
        },
        {
            title: "done",
            pills: [
                {
                    level: 0,
                    colSpan: "17 December 2018 -> 22 December 2018",
                    title: "Task 2",
                },
            ],
        },
        {
            title: "cancel",
            pills: [
                {
                    level: 0,
                    colSpan: "20 December 2018 -> 20 December 2018",
                    title: "Task 4",
                },
                { level: 0, colSpan: "27 December 2018 -> Out of bounds (35) ", title: "Task 3" },
            ],
        },
    ]);

    await selectBlock({
        sourceCell: getCell("17", "December 2018", "todo"),
        targetCell: getCell("17", "December 2018", "done"),
    });

    expect(".o_selection_box").toHaveText("2\nselected");

    await multiCreateClickAddButton();
    expect(".o_multi_create_popover").toHaveCount(1);
    await click(".o_multi_create_popover .o_form_view [name='name'] input");
    await edit("Time off");
    await multiCreatePopoverClickAddButton();

    expect(".o_multi_create_popover").toHaveCount(0);

    gridContent = getGridContent();
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 December 2018",
                    level: 0,
                    title: "Task 5",
                },
                {
                    colSpan: "17 December 2018 -> 17 December 2018",
                    level: 0,
                    title: "Time off",
                },
            ],
            title: "todo",
        },
        {
            title: "in_progress",
            pills: [
                { level: 0, colSpan: "01 December 2018 -> Out of bounds (32) ", title: "Task 1" },
                {
                    colSpan: "17 December 2018 -> 17 December 2018",
                    level: 1,
                    title: "Time off",
                },
                {
                    level: 1,
                    colSpan: "20 December 2018 -> 20 December 2018",
                    title: "Task 7",
                },
            ],
        },
        {
            title: "done",
            pills: [
                {
                    colSpan: "17 December 2018 -> 17 December 2018",
                    level: 0,
                    title: "Time off",
                },
                {
                    level: 1,
                    colSpan: "17 December 2018 -> 22 December 2018",
                    title: "Task 2",
                },
            ],
        },
        {
            title: "cancel",
            pills: [
                {
                    level: 0,
                    colSpan: "20 December 2018 -> 20 December 2018",
                    title: "Task 4",
                },
                { level: 0, colSpan: "27 December 2018 -> Out of bounds (35) ", title: "Task 3" },
            ],
        },
    ]);

    await selectBlock({
        sourceCell: getCell("17", "December 2018", "todo"),
        targetCell: getCell("17", "December 2018", "done"),
    });

    await click(".o_multi_selection_buttons .btn .fa-trash");
    await animationFrame();
    expect(".o_dialog .modal-body").toHaveText(
        "Are you sure you want to delete the 5 selected records?"
    );
    await contains(".o_dialog footer button:contains(Ok)").click();
    await animationFrame();

    gridContent = getGridContent();
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 December 2018",
                    level: 0,
                    title: "Task 5",
                },
            ],
            title: "todo",
        },
        {
            title: "in_progress",
            pills: [
                {
                    level: 0,
                    colSpan: "20 December 2018 -> 20 December 2018",
                    title: "Task 7",
                },
            ],
        },
        {
            title: "cancel",
            pills: [
                {
                    level: 0,
                    colSpan: "20 December 2018 -> 20 December 2018",
                    title: "Task 4",
                },
                { level: 0, colSpan: "27 December 2018 -> Out of bounds (35) ", title: "Task 3" },
            ],
        },
    ]);
});

test(`multi_create: no button "Delete" if no record selected`, async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                precision="{'day':'hour:full', 'week':'day:full', 'month':'day:full'}"
                multi_create_view="multi_create_form"
            />
        `,
        domain: Domain.FALSE.toList(),
    });
    const { rows } = getGridContent();
    expect(rows).toEqual([{}]);

    await selectBlock({
        sourceCell: getCell("17", "December 2018"),
        targetCell: getCell("18", "December 2018"),
    });
    expect(".o_selection_box").toHaveText("0\nselected");
    expect(".o_multi_selection_buttons .btn:contains(Add)").toHaveCount(1);
    expect(".o_multi_selection_buttons .btn .fa-trash").toHaveCount(0);
});

test("multi_create: selection with ctrl", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                precision="{'day':'hour:full', 'week':'day:full', 'month':'day:full'}"
                multi_create_view="multi_create_form"
            >
                <field name="progress"/>
            </gantt>
        `,
        groupBy: ["stage_id"],
    });
    let gridContent = getGridContent();
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 December 2018",
                    level: 0,
                    title: "Task 5",
                },
            ],
            title: "todo",
        },
        {
            title: "in_progress",
            pills: [
                { level: 0, colSpan: "01 December 2018 -> Out of bounds (32) ", title: "Task 1" },
                {
                    level: 1,
                    colSpan: "20 December 2018 -> 20 December 2018",
                    title: "Task 7",
                },
            ],
        },
        {
            title: "done",
            pills: [
                {
                    level: 0,
                    colSpan: "17 December 2018 -> 22 December 2018",
                    title: "Task 2",
                },
            ],
        },
        {
            title: "cancel",
            pills: [
                {
                    level: 0,
                    colSpan: "20 December 2018 -> 20 December 2018",
                    title: "Task 4",
                },
                { level: 0, colSpan: "27 December 2018 -> Out of bounds (35) ", title: "Task 3" },
            ],
        },
    ]);

    await selectBlock({
        sourceCell: getCell("17", "December 2018", "todo"),
        targetCell: getCell("17", "December 2018", "done"),
    });
    await animationFrame();

    expect(".o_selection_box").toHaveText("2\nselected");

    await keyDown("Control");
    await selectBlock({
        sourceCell: getCell("03", "December 2018", "todo"),
        targetCell: getCell("03", "December 2018", "cancel"),
    });
    await selectBlock({
        sourceCell: getCell("16", "December 2018", "todo"),
        targetCell: getCell("18", "December 2018", "in_progress"),
    });
    await click(getCell("03", "December 2018", "done"));
    await click(getCell("04", "December 2018", "done"));
    await animationFrame();
    await keyUp("Control");

    expect(".o_selection_box").toHaveText("3\nselected");
    await multiCreateClickAddButton();
    expect(".o_multi_create_popover").toHaveCount(1);
    await contains(".o_multi_create_popover .o_form_view [name='name'] input").edit("Time off");
    await focus(".o_multi_create_popover");
    await animationFrame();
    await multiCreatePopoverClickAddButton();

    expect(".o_multi_create_popover").toHaveCount(0);

    gridContent = getGridContent();
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 December 2018",
                    level: 0,
                    title: "Task 5",
                },
                {
                    colSpan: "03 December 2018 -> 03 December 2018",
                    level: 1,
                    title: "Time off",
                },
                {
                    colSpan: "16 December 2018 -> 16 December 2018",
                    level: 0,
                    title: "Time off",
                },
                {
                    colSpan: "17 December 2018 -> 17 December 2018",
                    level: 0,
                    title: "Time off",
                },
                {
                    colSpan: "18 December 2018 -> 18 December 2018",
                    level: 0,
                    title: "Time off",
                },
            ],
            title: "todo",
        },
        {
            pills: [
                {
                    colSpan: "01 December 2018 -> Out of bounds (32) ",
                    level: 0,
                    title: "Task 1",
                },
                {
                    colSpan: "03 December 2018 -> 03 December 2018",
                    level: 1,
                    title: "Time off",
                },
                {
                    colSpan: "16 December 2018 -> 16 December 2018",
                    level: 1,
                    title: "Time off",
                },
                {
                    colSpan: "17 December 2018 -> 17 December 2018",
                    level: 1,
                    title: "Time off",
                },
                {
                    colSpan: "18 December 2018 -> 18 December 2018",
                    level: 1,
                    title: "Time off",
                },
                {
                    colSpan: "20 December 2018 -> 20 December 2018",
                    level: 1,
                    title: "Task 7",
                },
            ],
            title: "in_progress",
        },
        {
            pills: [
                {
                    colSpan: "04 December 2018 -> 04 December 2018",
                    level: 0,
                    title: "Time off",
                },
                {
                    colSpan: "17 December 2018 -> 17 December 2018",
                    level: 0,
                    title: "Time off",
                },
                {
                    colSpan: "17 December 2018 -> 22 December 2018",
                    level: 1,
                    title: "Task 2",
                },
            ],
            title: "done",
        },
        {
            pills: [
                {
                    colSpan: "03 December 2018 -> 03 December 2018",
                    level: 0,
                    title: "Time off",
                },
                {
                    colSpan: "20 December 2018 -> 20 December 2018",
                    level: 0,
                    title: "Task 4",
                },
                {
                    colSpan: "27 December 2018 -> Out of bounds (35) ",
                    level: 0,
                    title: "Task 3",
                },
            ],
            title: "cancel",
        },
    ]);

    await keyDown("Control");
    await selectBlock({
        sourceCell: getCell("17", "December 2018", "todo"),
        targetCell: getCell("17", "December 2018", "done"),
    });
    await selectBlock({
        sourceCell: getCell("03", "December 2018", "todo"),
        targetCell: getCell("03", "December 2018", "cancel"),
    });
    await selectBlock({
        sourceCell: getCell("16", "December 2018", "todo"),
        targetCell: getCell("18", "December 2018", "in_progress"),
    });
    await click(getCell("03", "December 2018", "done"));
    await click(getCell("04", "December 2018", "done"));
    await animationFrame();
    await keyUp("Control");

    expect(".o_selection_box").toHaveText("14\nselected");

    await contains(".o_multi_selection_buttons .btn .fa-trash").click();
    await animationFrame();
    expect(".o_dialog .modal-body").toHaveText(
        "Are you sure you want to delete the 14 selected records?"
    );
    await contains(".o_dialog footer button:contains(Ok)").click();
    await animationFrame();

    gridContent = getGridContent();
    expect(gridContent.rows).toEqual([
        {
            title: "in_progress",
            pills: [
                {
                    title: "Task 7",
                    colSpan: "20 December 2018 -> 20 December 2018",
                    level: 0,
                },
            ],
        },
        {
            title: "cancel",
            pills: [
                {
                    title: "Task 4",
                    colSpan: "20 December 2018 -> 20 December 2018",
                    level: 0,
                },
                {
                    title: "Task 3",
                    colSpan: "27 December 2018 -> Out of bounds (35) ",
                    level: 0,
                },
            ],
        },
    ]);
});

test("multi_create: create single record from selection", async () => {
    Tasks._records = [];
    onRpc("tasks", "web_save", ({ args: [, record], kwargs: { context } }) => {
        expect.step(`web_save`);
        expect.step(`name: ${record.name}`);
        expect.step(`start: ${context.default_start}`);
        expect.step(`stop: ${context.default_stop}`);
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                precision="{'day':'hour:full', 'week':'day:full', 'month':'day:full'}"
                multi_create_view="multi_create_form"
                create="1"
            >
                <field name="progress"/>
            </gantt>
        `,
        groupBy: ["stage_id"],
    });
    let gridContent = getGridContent();
    expect(gridContent.rows).toEqual([{ title: "" }]);

    await selectBlock({
        sourceCell: getCell("17", "December 2018"),
        targetCell: getCell("18", "December 2018"),
    });
    await animationFrame();
    await keyDown("Control");
    await selectBlock({
        sourceCell: getCell("03", "December 2018"),
        targetCell: getCell("04", "December 2018"),
    });
    await animationFrame();
    await keyUp("Control");
    expect(".o_dialog").toHaveCount(0);

    await contains(".o_gantt_button_add").click();
    await animationFrame();
    expect(".o_dialog").toHaveCount(1);

    await contains(".o_dialog .o_input:eq(0)").edit("a name");
    await contains(".o_dialog .o_form_button_save").click();
    expect(".o_dialog").toHaveCount(0);
    gridContent = getGridContent();
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "03 December 2018 -> 04 December 2018",
                    level: 0,
                    title: "a name",
                },
            ],
            title: "Undefined Stage",
        },
    ]);
    expect.verifySteps([
        "web_save",
        `name: a name`,
        `start: 2018-12-02 23:00:00`,
        `stop: 2018-12-04 23:00:00`,
    ]);
});

test("multi_create: create single record if no selection", async () => {
    Tasks._records = [];
    onRpc("tasks", "web_save", ({ args: [, record], kwargs: { context } }) => {
        expect.step(`web_save`);
        expect.step(`name: ${record.name}`);
        expect.step(`start: ${context.default_start}`);
        expect.step(`stop: ${context.default_stop}`);
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                precision="{'day':'hour:full', 'week':'day:full', 'month':'day:full'}"
                multi_create_view="multi_create_form"
                create="1"
            >
                <field name="progress"/>
            </gantt>
        `,
        groupBy: ["stage_id"],
    });
    let gridContent = getGridContent();
    expect(gridContent.rows).toEqual([{ title: "" }]);
    expect(".o_multi_selection_buttons").toHaveCount(0);

    await contains(".o_gantt_button_add").click();
    await animationFrame();
    expect(".o_dialog").toHaveCount(1);

    await contains(".o_dialog .o_input:eq(0)").edit("a name");
    await contains(".o_dialog .o_form_button_save").click();
    expect(".o_dialog").toHaveCount(0);
    gridContent = getGridContent();
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "01 December 2018 -> Out of bounds (32) ",
                    level: 0,
                    title: "a name",
                },
            ],
            title: "Undefined Stage",
        },
    ]);
    expect.verifySteps([
        "web_save",
        `name: a name`,
        `start: 2018-11-30 23:00:00`,
        `stop: 2018-12-31 23:00:00`,
    ]);
});

test(`multi_create: no plan button if plan="0"`, async () => {
    Tasks._records = [];
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                precision="{'day':'hour:full', 'week':'day:full', 'month':'day:full'}"
                multi_create_view="multi_create_form"
                plan="0"
            >
                <field name="progress"/>
            </gantt>
        `,
        groupBy: ["stage_id"],
    });

    await click(getCell("17", "December 2018"));
    await animationFrame();

    expect(".o_multi_selection_buttons > button").toHaveCount(1);
    expect(".o_multi_selection_buttons > button").toHaveText("Add");
});

test(`multi_create: plan button if plan="1" and one cell selected`, async () => {
    Tasks._records = [{ id: 1, start: false, stop: false, progress: 0, name: "a name" }];
    Tasks._views["list"] = `<list><field name="name"/></list>`;
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                precision="{'day':'hour:full', 'week':'day:full', 'month':'day:full'}"
                multi_create_view="multi_create_form"
                plan="1"
            >
                <field name="progress"/>
            </gantt>
        `,
        groupBy: ["stage_id"],
    });
    let gridContent = getGridContent();
    expect(gridContent.rows).toEqual([{ title: "" }]);

    await click(getCell("17", "December 2018"));
    await animationFrame();

    expect(".o_multi_selection_buttons > button").toHaveCount(2);
    expect(".o_multi_selection_buttons > button:first").toHaveText("Add");
    expect(".o_multi_selection_buttons > button:last").toHaveText("Plan");
    expect(".o_dialog").toHaveCount(0);

    await contains(".o_multi_selection_buttons > button:last").click();
    expect(".o_dialog").toHaveCount(1);

    await contains(".o_data_cell").click(); // select record
    expect(".o_dialog").toHaveCount(0);
    gridContent = getGridContent();
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "17 December 2018 -> 17 December 2018",
                    level: 0,
                    title: "a name",
                },
            ],
            title: "Undefined Stage",
        },
    ]);
});

test(`multi_create: no plan button if plan="1" and more that one cell selected`, async () => {
    Tasks._records = [];
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                precision="{'day':'hour:full', 'week':'day:full', 'month':'day:full'}"
                multi_create_view="multi_create_form"
                plan="1"
            >
                <field name="progress"/>
            </gantt>
        `,
        groupBy: ["stage_id"],
    });

    await selectBlock({
        sourceCell: getCell("17", "December 2018"),
        targetCell: getCell("18", "December 2018"),
    });
    await animationFrame();

    expect(".o_multi_selection_buttons > button").toHaveCount(1);
    expect(".o_multi_selection_buttons > button:first").toHaveText("Add");
});

test("multi_create: can start selection over locked pills", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                precision="{'day':'hour:full', 'week':'day:full', 'month':'day:full'}"
                multi_create_view="multi_create_form"
                disable_drag_drop="1"
            >
                <field name="progress"/>
            </gantt>
        `,
        groupBy: ["stage_id"],
    });
    let gridContent = getGridContent();
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 December 2018",
                    level: 0,
                    title: "Task 5",
                },
            ],
            title: "todo",
        },
        {
            title: "in_progress",
            pills: [
                { level: 0, colSpan: "01 December 2018 -> Out of bounds (32) ", title: "Task 1" },
                {
                    level: 1,
                    colSpan: "20 December 2018 -> 20 December 2018",
                    title: "Task 7",
                },
            ],
        },
        {
            title: "done",
            pills: [
                {
                    level: 0,
                    colSpan: "17 December 2018 -> 22 December 2018",
                    title: "Task 2",
                },
            ],
        },
        {
            title: "cancel",
            pills: [
                {
                    level: 0,
                    colSpan: "20 December 2018 -> 20 December 2018",
                    title: "Task 4",
                },
                { level: 0, colSpan: "27 December 2018 -> Out of bounds (35) ", title: "Task 3" },
            ],
        },
    ]);

    // Equivalent to select from 01 December todo to 02 December done
    const { drop } = await dragPill("Task 5");
    await drop({ row: "done", columnHeader: "02", groupHeader: "December 2018" });

    expect(".o_selection_box").toHaveText("2\nselected");

    await multiCreateClickAddButton();
    expect(".o_multi_create_popover").toHaveCount(1);
    await click(".o_multi_create_popover .o_form_view [name='name'] input");
    await edit("Time off");
    await multiCreatePopoverClickAddButton();

    expect(".o_multi_create_popover").toHaveCount(0);

    gridContent = getGridContent();
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "01 December 2018 -> 04 December 2018",
                    level: 0,
                    title: "Task 5",
                },
                {
                    title: "Time off",
                    colSpan: "01 December 2018 -> 01 December 2018",
                    level: 1,
                },
                {
                    title: "Time off",
                    colSpan: "02 December 2018 -> 02 December 2018",
                    level: 1,
                },
            ],
            title: "todo",
        },
        {
            title: "in_progress",
            pills: [
                { level: 0, colSpan: "01 December 2018 -> Out of bounds (32) ", title: "Task 1" },
                {
                    title: "Time off",
                    colSpan: "01 December 2018 -> 01 December 2018",
                    level: 1,
                },
                {
                    title: "Time off",
                    colSpan: "02 December 2018 -> 02 December 2018",
                    level: 1,
                },
                {
                    level: 1,
                    colSpan: "20 December 2018 -> 20 December 2018",
                    title: "Task 7",
                },
            ],
        },
        {
            title: "done",
            pills: [
                {
                    title: "Time off",
                    colSpan: "01 December 2018 -> 01 December 2018",
                    level: 0,
                },
                {
                    title: "Time off",
                    colSpan: "02 December 2018 -> 02 December 2018",
                    level: 0,
                },
                {
                    title: "Task 2",
                    level: 0,
                    colSpan: "17 December 2018 -> 22 December 2018",
                },
            ],
        },
        {
            title: "cancel",
            pills: [
                {
                    level: 0,
                    colSpan: "20 December 2018 -> 20 December 2018",
                    title: "Task 4",
                },
                { level: 0, colSpan: "27 December 2018 -> Out of bounds (35) ", title: "Task 3" },
            ],
        },
    ]);
});
