import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click, edit, press } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";

import { contains, mailModels } from "@mail/../tests/mail_test_helpers";
import { ProjectProject, defineProjectModels } from "@project/../tests/project_models";
import { onRpc, removeFacet } from "@web/../tests/web_test_helpers";
import { getGridContent, mountGanttView } from "@web_gantt/../tests/web_gantt_test_helpers";
import { ProjectTask } from "./task_gant_model";

defineProjectModels();
describe.current.tags("desktop");

beforeEach(() => {
    mailModels.ResUsers._records = [
        { id: 1, name: "User1" },
        { id: 2, name: "User2" },
        ...mailModels.ResUsers._records,
    ];
    ProjectProject._records = [
        { id: 1, name: "service" },
        { id: 2, name: "sign" },
    ];
    ProjectTask._records = [
        {
            id: 1,
            name: "Task 1",
            planned_date_begin: "2019-03-12 06:30:00",
            date_deadline: "2019-03-12 12:30:00",
            project_id: 1,
            user_ids: [1],
            planning_overlap: "Task 1 has 1 tasks at the same time.",
        },
        {
            id: 2,
            name: "Task 2",
            planned_date_begin: "2019-03-12 06:30:00",
            date_deadline: "2019-03-12 12:30:00",
            project_id: 1,
            user_ids: [1],
            planning_overlap: "Task 2 has 1 tasks at the same time.",
        },
        {
            id: 3,
            name: "Task 3",
            planned_date_begin: "2019-03-11 10:30:00",
            date_deadline: "2019-03-11 12:30:00",
            project_id: 1,
            user_ids: [2],
        },
        {
            id: 4,
            name: "Task 4",
            planned_date_begin: "2019-03-14 10:30:00",
            date_deadline: "2019-03-14 12:30:00",
            project_id: 2,
            user_ids: [2],
        },
        {
            id: 5,
            name: "Task 5",
            planned_date_begin: "2019-03-13 10:30:00",
            date_deadline: "2019-03-13 12:30:00",
            project_id: 2,
        },
    ];
});

test("Unassigned tasks will show when search for assignee", async () => {
    onRpc("project.task", "get_gantt_data", ({ kwargs }) => {
        kwargs.domain = (kwargs.domain || []).map((d) =>
            Array.isArray(d) && d.length === 3 && d[0] === "user_ids.name"
                ? ["user_ids", "=", 1]
                : d
        );
    });

    await mountGanttView({
        resModel: "project.task",
        type: "gantt",
        arch: `
            <gantt
                js_class="task_gantt"
                date_start="planned_date_begin"
                date_stop="date_deadline"
                default_scale="week"
            />
        `,
        groupBy: ["user_ids"],
        searchViewArch: `
            <search>
                <field name="user_ids" filter_domain="[('user_ids.name', 'ilike', self)]"/>
            </search>
        `,
    });
    await contains(".o_gantt_row_title", { count: 3 });
    expect(getGridContent().rows).toEqual([
        {
            title: "👤 Unassigned",
            pills: [
                {
                    title: "Task 5",
                    level: 0,
                    colSpan:
                        "Wednesday 13 Week 11, Mar 10 - Mar 16 -> Wednesday 13 Week 11, Mar 10 - Mar 16",
                },
            ],
        },
        {
            title: "User1",
            pills: [
                {
                    title: "Task 1",
                    level: 0,
                    colSpan:
                        "Tuesday 12 Week 11, Mar 10 - Mar 16 -> Tuesday 12 Week 11, Mar 10 - Mar 16",
                },
                {
                    title: "Task 2",
                    level: 1,
                    colSpan:
                        "Tuesday 12 Week 11, Mar 10 - Mar 16 -> Tuesday 12 Week 11, Mar 10 - Mar 16",
                },
            ],
        },
        {
            title: "User2",
            pills: [
                {
                    title: "Task 3",
                    level: 0,
                    colSpan:
                        "Monday 11 Week 11, Mar 10 - Mar 16 -> Monday 11 Week 11, Mar 10 - Mar 16",
                },
                {
                    title: "Task 4",
                    level: 0,
                    colSpan:
                        "Thursday 14 Week 11, Mar 10 - Mar 16 -> Thursday 14 Week 11, Mar 10 - Mar 16",
                },
            ],
        },
    ]);
    await click(".o_searchview_input");
    await edit("User1");
    await animationFrame();
    await press("Enter");
    await contains(".o_gantt_row_title", { count: 2 });
    expect(getGridContent().rows).toEqual([
        {
            title: "👤 Unassigned",
            pills: [
                {
                    title: "Task 5",
                    level: 0,
                    colSpan:
                        "Wednesday 13 Week 11, Mar 10 - Mar 16 -> Wednesday 13 Week 11, Mar 10 - Mar 16",
                },
            ],
        },
        {
            title: "User1",
            pills: [
                {
                    title: "Task 1",
                    level: 0,
                    colSpan:
                        "Tuesday 12 Week 11, Mar 10 - Mar 16 -> Tuesday 12 Week 11, Mar 10 - Mar 16",
                },
                {
                    title: "Task 2",
                    level: 1,
                    colSpan:
                        "Tuesday 12 Week 11, Mar 10 - Mar 16 -> Tuesday 12 Week 11, Mar 10 - Mar 16",
                },
            ],
        },
    ]);
});

test("Tasks in conflicting are highlighted, while non-conflicting tasks are in muted.", async () => {
    ProjectTask._views = {
        form: `
            <form>
                <field name="name"/>
                <field name="user_ids" widget="many2many_tags"/>
                <field name="project_id"/>
            </form>
        `,
    };

    await mountGanttView({
        resModel: "project.task",
        type: "gantt",
        arch: `
            <gantt
                js_class="task_gantt"
                date_start="planned_date_begin"
                date_stop="date_deadline"
                default_scale="week"
            />
        `,
        groupBy: ["user_ids"],
        searchViewArch: `
            <search>
                <filter name="conflict_task" string="Tasks in Conflict" context="{'highlight_conflicting_task': 1}"/>
            </search>
        `,
        context: { search_default_conflict_task: 1 },
    });

    await contains(".o_gantt_pill", { count: 5 });
    await contains(".o_gantt_pill[class*='opacity-25']", { count: 3 });
    expect(".o_gantt_pill.opacity-25").toHaveText(/Task (5|3|4)/i);
    expect(".o_gantt_pill:not(.opacity-25)").toHaveText(/Task (1|2)/i);
    removeFacet("Tasks in Conflict");
    await contains(".o_gantt_pill", { count: 5 });
    await contains(".o_gantt_pill[class*='opacity-25']", { count: 0 });
});
