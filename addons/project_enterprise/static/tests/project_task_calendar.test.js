import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { queryFirst } from "@odoo/hoot-dom";
import { mockDate } from "@odoo/hoot-mock";
import { contains, mountView, onRpc } from "@web/../tests/web_test_helpers";
import { defineProjectModels } from "@project/../tests/project_models";
import { ProjectTask } from "@project_enterprise/../tests/task_gant_model";
import { serializeDateTime } from "@web/core/l10n/dates";

describe.current.tags("desktop");
defineProjectModels();

beforeEach(() => {
    mockDate("2016-11-12 08:00:00", 0);
    onRpc("has_access", () => true);
});

ProjectTask._views.form = `
    <form>
        <field name="id"/>
        <field name="name"/>
        <field name="planned_date_begin"/>
        <field name="date_deadline" widget="daterange" options="{'start_date_field': 'planned_date_begin'}"/>
    </form>
`;

const calendarMountParams = {
    resModel: "project.task",
    type: "calendar",
    arch: `
        <calendar
            date_start="planned_date_start"
            date_stop="date_deadline"
            event_open_popup="1"
            mode="month"
            js_class="project_task_calendar"
            quick_create="0"
        />
    `,
    config: { views: [[false, "form"]] },
};

test("Drag and drop task to schedule in month scale", async () => {
    let expectedDate = null;

    onRpc("project.task", "search_read", ({ method }) => {
        expect.step(method);
    });
    onRpc("project.task", "web_search_read", ({ method }) => {
        expect.step("fetch tasks to schedule");
    });
    onRpc("project.task", "plan_task_in_calendar", ({ args }) => {
        const [taskIds, vals] = args;
        expect(taskIds).toEqual([1]);
        const dateDeadline = expectedDate.set({ hours: 19 });
        expect(vals).toEqual({
            date_deadline: serializeDateTime(dateDeadline),
        });
        expect.step("plan task");
    });
    await mountView({
        ...calendarMountParams,
        context: { default_project_id: 1 },
    });
    expect(".o_task_to_plan_draggable").toHaveCount(2);
    const { drop, moveTo } = await contains(".o_task_to_plan_draggable:first").drag();
    const dateCell = queryFirst(".fc-day.fc-day-today.fc-daygrid-day");
    expectedDate = luxon.DateTime.fromISO(dateCell.dataset.date);
    await moveTo(dateCell);
    expect(dateCell).toHaveClass("o-highlight");
    await drop();
    expect.verifySteps(["search_read", "fetch tasks to schedule", "plan task", "search_read"]);
    expect(".o_task_to_plan_draggable").toHaveCount(1);
    expect(".o_task_to_plan_draggable").toHaveText("Regular task 2");
});
