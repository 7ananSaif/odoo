import { mailModels } from "@mail/../tests/mail_test_helpers";
import { beforeEach, describe, destroy, expect, test } from "@odoo/hoot";
import { hover, keyDown, queryAll, queryAllTexts, queryOne } from "@odoo/hoot-dom";
import { animationFrame, mockDate } from "@odoo/hoot-mock";
import {
    clickModalButton,
    contains,
    defineModels,
    fields,
    mockService,
    models,
    onRpc,
} from "@web/../tests/web_test_helpers";
import {
    clickCell,
    dragPill,
    getGridContent,
    hoverGridCell,
    mountGanttView,
    SELECTORS,
} from "@web_gantt/../tests/web_gantt_test_helpers";

import {
    defineProjectModels,
    projectModels,
    ProjectProject,
} from "@project/../tests/project_models";

describe.current.tags("desktop");

const ganttViewParams = {
    arch: '<gantt js_class="task_gantt" date_start="planned_date_begin" date_stop="date_deadline"/>',
    resModel: "project.task",
    groupBy: ["user_ids"],
};

beforeEach(() => {
    mockDate("2021-06-22 08:00:00");
    mailModels.ResUsers._records.push({ id: 100, name: "Jane Doe" }, { id: 101, name: "John Doe" });
    ProjectProject._records = [
        { id: 1, name: "My Project", date_start: "2021-01-01", date: "2021-06-24" },
    ];
});

class Task extends projectModels.ProjectTask {
    stuff_id = fields.Many2one({ string: "Stuff", relation: "stuff" });

    _records = [
        {
            id: 1,
            name: "Blop",
            planned_date_begin: "2021-06-14 08:00:00",
            date_deadline: "2021-06-24 08:00:00",
            user_ids: [100],
            project_id: 1,
            milestone_id: 3,
        },
        {
            id: 2,
            name: "Yop",
            planned_date_begin: "2021-06-02 08:00:00",
            date_deadline: "2021-06-12 08:00:00",
            user_ids: [101],
            stuff_id: 1,
            project_id: 1,
        },
    ];
    _views = {
        list: '<list><field name="name"/></list>',
        form: '<form><field name="name"/></form>',
    };
}

class Stuff extends models.Model {
    name = fields.Char();

    _records = [{ id: 1, name: "Bruce Willis" }];
}

projectModels.ProjectTask = Task;

defineModels([Stuff]);
defineProjectModels();

test("not user_ids grouped: empty groups are displayed first and user avatar is not displayed", async () => {
    await mountGanttView({ ...ganttViewParams, groupBy: ["stuff_id"] });
    expect(queryAllTexts(".o_gantt_row_headers .o_gantt_row_title")).toEqual([
        "Undefined Stuff",
        "Bruce Willis",
    ]);
    expect(".o_gantt_row_headers .o-mail-Avatar").toHaveCount(0);
});

test("Unschedule button is displayed", async () => {
    onRpc(({ method, model }) => {
        if (model === "project.task" && method == "action_unschedule_task") {
            expect.step("unschedule task");
            return false;
        }
    });
    await mountGanttView({
        arch: `
            <gantt date_start="planned_date_begin" date_stop="date_deadline">
                <templates>
                    <t t-name="gantt-popover">
                        <footer>
                            <button name="action_unschedule_task" type="object" string="Unschedule"
                                class="btn btn-sm btn-secondary"/>
                        </footer>
                    </t>
                </templates>
            </gantt>
        `,
        resModel: "project.task",
    });
    await contains(".o_gantt_pill").click();
    expect(".btn.btn-sm.btn-secondary").toHaveCount(1);
    expect(".btn.btn-sm.btn-secondary").toHaveText("Unschedule");
    await contains(".btn.btn-sm.btn-secondary").click();
    expect.verifySteps(["unschedule task"]);
});

test("not user_ids grouped: no empty group if no records", async () => {
    // delete the record having no stuff_id
    Task._records.splice(0, 1);
    await mountGanttView({ ...ganttViewParams, groupBy: ["stuff_id"] });
    expect(queryAllTexts(".o_gantt_row_headers .o_gantt_row_title")).toEqual(["Bruce Willis"]);
});

test("user_ids grouped: specific empty group added, even if no records", async () => {
    await mountGanttView(ganttViewParams);
    expect(queryAllTexts(".o_gantt_row_headers .o_gantt_row_title")).toEqual(
        ["👤 Unassigned", "Jane Doe", "John Doe"],
        {
            message:
                "'👤 Unassigned' should be the first group, even if no record exist without user_ids",
        }
    );
    expect(".o_gantt_row_headers .o-mail-Avatar").toHaveCount(2);
});

test("[user_ids, ...] grouped", async () => {
    // add an unassigned task (no user_ids) that has a linked stuff
    Task._records.push({
        id: 3,
        name: "Gnop",
        planned_date_begin: "2021-06-02 08:00:00",
        date_deadline: "2021-06-12 08:00:00",
        stuff_id: 1,
    });
    await mountGanttView({ ...ganttViewParams, groupBy: ["user_ids", "stuff_id"] });
    expect(queryAllTexts(".o_gantt_row_headers .o_gantt_row_title")).toEqual([
        "👤 Unassigned",
        "Undefined Stuff",
        "Bruce Willis",
        "Jane Doe",
        "Undefined Stuff",
        "John Doe",
        "Bruce Willis",
    ]);
});

test("[..., user_ids(, ...)] grouped", async () => {
    await mountGanttView({ ...ganttViewParams, groupBy: ["stuff_id", "user_ids"] });
    expect(queryAllTexts(".o_gantt_row_headers .o_gantt_row_title")).toEqual([
        "Undefined Stuff",
        "👤 Unassigned",
        "Jane Doe",
        "Bruce Willis",
        "👤 Unassigned",
        "John Doe",
    ]);
});

test('Empty groupby "Assigned To" and "Project" can be rendered', async function (assert) {
    Task._records = [];
    await mountGanttView({ ...ganttViewParams, groupBy: ["user_ids", "project_id"] });
    expect(queryAllTexts(".o_gantt_row_headers .o_gantt_row_title")).toEqual([
        "👤 Unassigned",
        "🔒 Private",
    ]);
});

test("progress bar has the correct unit", async () => {
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        const result = parent();
        expect(kwargs.progress_bar_fields).toEqual(["user_ids"]);
        result.progress_bars.user_ids = {
            100: { value: 100, max_value: 100 },
        };
        return result;
    });
    await mountGanttView({
        arch: '<gantt js_class="task_gantt" date_start="planned_date_begin" date_stop="date_deadline" progress_bar="user_ids"/>',
        resModel: "project.task",
        type: "gantt",
        groupBy: ["user_ids"],
    });
    expect(SELECTORS.progressBar).toHaveCount(1);
    expect(SELECTORS.progressBarBackground).toHaveCount(1);
    expect(queryOne(SELECTORS.progressBarBackground).style.width).toBe("100%");
    expect(SELECTORS.progressBarForeground).toHaveCount(0);
    await hoverGridCell("10", "June 2021", "Jane Doe");
    expect(SELECTORS.progressBarForeground).toHaveCount(1);
    expect(SELECTORS.progressBarForeground).toHaveText("100h / 100h");
});

test("open a dialog to schedule task", async () => {
    Task._records.push({
        id: 51,
        name: "Task 51",
        project_id: 1,
        user_ids: [100],
    });
    onRpc("schedule_tasks", () => {
        expect.step("schedule_tasks");
        return {};
    });
    await mountGanttView({
        arch: '<gantt date_start="planned_date_begin" date_stop="date_deadline" js_class="task_gantt" />',
        resModel: "project.task",
        type: "gantt",
    });
    await clickCell("10", "June 2021");
    await contains(".modal .o_list_view tbody tr:nth-child(1) input").click();
    await animationFrame();
    expect(".modal .o_list_view .o_data_row").toHaveClass("o_data_row_selected");
    await contains(".modal footer .o_auto_plan_button").click();
    expect.verifySteps(["schedule_tasks"]);
});

test("Lines are displayed in alphabetic order, except for the first one", async () => {
    for (const user of [
        { id: 102, name: "Omega" },
        { id: 103, name: "Theta" },
        { id: 104, name: "Rho" },
        { id: 105, name: "Zeta" },
        { id: 106, name: "Kappa" },
    ]) {
        mailModels.ResUsers._records.push(user);
        Task._records.push({
            id: user.id,
            name: "Citron en Suédois",
            planned_date_begin: "2021-06-02 08:00:00",
            date_deadline: "2021-06-12 08:00:00",
            project_id: 1,
            user_ids: [user.id],
        });
    }
    await mountGanttView(ganttViewParams);
    expect(queryAllTexts(".o_gantt_row_headers .o_gantt_row_title")).toEqual(
        ["👤 Unassigned", "Jane Doe", "John Doe", "Kappa", "Omega", "Rho", "Theta", "Zeta"],
        {
            message:
                "The lines should be sorted by alphabetical order ('👤 Unassigned' is always first)",
        }
    );
});

test("Display milestones deadline in project.task gantt view", async () => {
    onRpc("get_all_deadlines", function () {
        const [milestone1, milestone2] = this.env["project.milestone"].browse([1, 2]);
        return {
            milestone_id: [
                {
                    ...milestone1,
                    project_id: [1, "My Project"],
                },
                {
                    ...milestone2,
                    project_id: [1, "My Project"],
                },
            ],
            project_id: [],
        };
    });
    await mountGanttView({
        ...ganttViewParams,
    });
    expect(".o_project_milestone_diamond").toHaveCount(2);
    expect(".o_project_milestone_diamond .o_milestones_reached").toHaveCount(1);
    expect(".o_project_milestone_diamond.o_unreached_milestones").toHaveCount(1);
    await hover(".o_project_milestone_diamond");
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(1);
    expect(".o_popover u").toHaveText("My Project");
    expect(".o_popover .o_milestones_reached").toHaveCount(1);
    expect(".o_popover strong").toHaveText("Milestone 1");
    await hover(".o_project_milestone_diamond.o_unreached_milestones");
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(1);
    expect(".o_popover u").toHaveText("My Project");
    expect(".o_popover .o_unreached_milestones").toHaveCount(1);
    expect(".o_popover strong").toHaveText("Milestone 2");
});

test("Display milestones deadline in gantt view of tasks in a project", async () => {
    onRpc("get_all_deadlines", function () {
        const [milestone1, milestone2] = this.env["project.milestone"].browse([1, 2]);
        return {
            milestone_id: [
                {
                    ...milestone1,
                    project_id: [1, "My Project"],
                },
                {
                    ...milestone2,
                    project_id: [1, "My Project"],
                },
            ],
            project_id: [],
        };
    });
    await mountGanttView({
        ...ganttViewParams,
        context: {
            default_project_id: 1,
        },
    });
    expect(".o_project_milestone_diamond").toHaveCount(2);
    expect(".o_project_milestone_diamond .o_milestones_reached").toHaveCount(1);
    expect(".o_project_milestone_diamond.o_unreached_milestones").toHaveCount(1);
    await hover(".o_project_milestone_diamond");
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(0);
    expect(".o_popover .o_milestones_reached").toHaveCount(1);
    expect(".o_popover strong").toHaveText("Milestone 1");
    await hover(".o_project_milestone_diamond.o_unreached_milestones");
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(0);
    expect(".o_popover .o_unreached_milestones").toHaveCount(1);
    expect(".o_popover strong").toHaveText("Milestone 2");
});

test("Display project deadline in the gantt view of task", async () => {
    ProjectProject._records.push({
        id: 2,
        name: "Other Project",
        date_start: "2021-06-12",
        date: "2021-06-28",
    });
    await mountGanttView(ganttViewParams);

    expect(".o_gantt_header_cell .o_project_startdate_circle").toHaveCount(1);
    expect(".o_gantt_header_cell .o_project_deadline_circle").toHaveCount(2);
    expect(".o_popover").toHaveCount(0);
    await hover(".o_gantt_header_cell .o_project_startdate_circle");
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(1);
    expect(".o_popover .popover-body u").toHaveText("Other Project");
    expect(".o_popover .popover-body em").toHaveText("Project start");
    const [myProjectDeadlineCircleEl, otherProjectDeadlineCircleEl] = queryAll(
        ".o_gantt_header_cell .o_project_deadline_circle"
    );
    await hover(myProjectDeadlineCircleEl);
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(1);
    expect(".o_popover u").toHaveText("My Project");
    expect(".o_popover .popover-body em").toHaveText("Project due");

    await hover(otherProjectDeadlineCircleEl);
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(1);
    expect(".o_popover u").toHaveText("Other Project");
    expect(".o_popover .popover-body em").toHaveText("Project due");
});

test("Display project and milestones deadline in the gantt view of task", async () => {
    ProjectProject._records.push({
        id: 2,
        name: "Other Project",
        date_start: "2021-06-12",
        date: "2021-06-28",
    });
    onRpc("get_all_deadlines", function () {
        const [milestone1, milestone2] = this.env["project.milestone"].browse([1, 2]);
        return {
            milestone_id: [
                {
                    ...milestone1,
                    project_id: [1, "My Project"],
                },
                {
                    ...milestone2,
                    project_id: [1, "My Project"],
                },
            ],
            project_id: this.env["project.project"].search_read(),
        };
    });
    await mountGanttView(ganttViewParams);

    expect(".o_project_milestone_diamond").toHaveCount(2);
    expect(".o_project_milestone_diamond .o_milestones_reached").toHaveCount(1);
    expect(".o_project_milestone_diamond.o_unreached_milestones").toHaveCount(1);
    await hover(".o_project_milestone_diamond");
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(1);
    expect(".o_popover u").toHaveText("My Project");
    expect(".o_popover .o_milestones_reached").toHaveCount(1);
    expect(".o_popover strong").toHaveText("Milestone 1");
    await hover(".o_project_milestone_diamond.o_unreached_milestones");
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(1);
    expect(".o_popover u").toHaveText("My Project");
    expect(".o_popover .o_unreached_milestones").toHaveCount(1);
    expect(".o_popover strong").toHaveText("Milestone 2");

    expect(".o_gantt_header_cell .o_project_startdate_circle").toHaveCount(1);
    expect(".o_gantt_header_cell .o_project_deadline_circle").toHaveCount(2);
    await hover(".o_gantt_header_cell .o_project_startdate_circle");
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(1);
    expect(".o_popover .popover-body u").toHaveText("Other Project");
    expect(".o_popover .popover-body em").toHaveText("Project start");
    const [myProjectDeadlineCircleEl, otherProjectDeadlineCircleEl] = queryAll(
        ".o_gantt_header_cell .o_project_deadline_circle"
    );
    await hover(myProjectDeadlineCircleEl);
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(1);
    expect(".o_popover u").toHaveText("My Project");
    expect(".o_popover .popover-body em").toHaveText("Project due");

    await hover(otherProjectDeadlineCircleEl);
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(1);
    expect(".o_popover u").toHaveText("Other Project");
    expect(".o_popover .popover-body em").toHaveText("Project due");
});

test("Display project deadline and milestone date in the same date", async () => {
    onRpc("get_all_deadlines", function () {
        const [milestone3] = this.env["project.milestone"].browse(3);
        return {
            milestone_id: [
                {
                    ...milestone3,
                    project_id: [1, "My Project"],
                },
            ],
            project_id: this.env["project.project"].search_read(),
        };
    });
    await mountGanttView(ganttViewParams);

    expect(
        ".o_gantt_header_cell .o_project_milestone_diamond.o_project_deadline_milestone"
    ).toHaveCount(1);
    await hover(".o_gantt_header_cell .o_project_milestone_diamond.o_project_deadline_milestone");
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(1);
    expect(".o_popover u").toHaveText("My Project");
    expect(".o_popover .popover-body").toHaveCount(1);
    expect(".o_popover .popover-body em").toHaveText("Project due");
    expect(".o_popover .popover-body strong").toHaveText("Milestone 3");
});

test("Display 2 milestones in different project at the same date", async () => {
    ProjectProject._records.push({
        id: 2,
        name: "Other Project",
    });
    projectModels.ProjectMilestone._records.push({
        id: 4,
        name: "Milestone 4",
        deadline: "2021-06-24",
        project_id: 2,
    });
    onRpc("get_all_deadlines", function () {
        const [milestone3, milestone4] = this.env["project.milestone"].browse([3, 4]);
        return {
            milestone_id: [
                {
                    ...milestone3,
                    project_id: [1, "My Project"],
                },
                {
                    ...milestone4,
                    project_id: [2, "Other Project"],
                },
            ],
            project_id: [],
        };
    });

    await mountGanttView(ganttViewParams);

    expect(".o_project_milestone_diamond").toHaveCount(1);
    await hover(".o_project_milestone_diamond");
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(2);
    expect(queryAllTexts(".o_popover u")).toEqual(["My Project", "Other Project"]);
    expect(".o_popover .popover-body i.fa-square-o").toHaveCount(2);
    expect(".o_popover .popover-body strong").toHaveCount(2);
    expect(queryAllTexts(".o_popover .popover-body strong")).toEqual([
        "Milestone 3",
        "Milestone 4",
    ]);
    expect(queryAllTexts(".o_popover .popover-body")).toEqual([
        "My Project\nMilestone 3\nOther Project\nMilestone 4",
    ]);
});

test("Display project deadline of 2 projects with the same deadline", async () => {
    ProjectProject._records.push({
        id: 2,
        name: "Other Project",
        date_start: "2021-05-12",
        date: "2021-06-24",
    });

    await mountGanttView(ganttViewParams);

    expect(".o_gantt_header_cell .o_project_deadline_circle").toHaveCount(1);
    await hover(".o_gantt_header_cell .o_project_deadline_circle");
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(2);
    expect(queryAllTexts(".o_popover u")).toEqual(["My Project", "Other Project"]);
    expect(".o_popover .popover-body em").toHaveCount(2);
    expect(queryAllTexts(".o_popover .popover-body em")).toEqual(["Project due", "Project due"]);
    expect(queryAllTexts(".o_popover .popover-body")).toEqual([
        "My Project\nProject due\nOther Project\nProject due",
    ]);
});

test("Display project deadline one day before the start date of the other project", async () => {
    ProjectProject._records.push({
        id: 2,
        name: "Other Project",
        date_start: "2021-06-25",
        date: "2021-10-01",
    });

    await mountGanttView(ganttViewParams);

    expect(".o_gantt_header_cell .o_project_deadline_circle").toHaveCount(1);
    await hover(".o_gantt_header_cell .o_project_deadline_circle");
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover u").toHaveCount(2);
    expect(queryAllTexts(".o_popover u")).toEqual(["My Project", "Other Project"]);
    expect(".o_popover .popover-body em").toHaveCount(2);
    expect(queryAllTexts(".o_popover .popover-body em")).toEqual(["Project due", "Project start"]);
    expect(queryAllTexts(".o_popover .popover-body")).toEqual([
        "My Project\nProject due\nOther Project\nProject start",
    ]);
});

test("Copy pill in another row", async () => {
    await mountGanttView(ganttViewParams);

    expect(getGridContent().rows).toEqual([
        {
            title: "👤 Unassigned",
        },
        {
            title: "Jane Doe",
            pills: [{ title: "Blop", level: 0, colSpan: "14 June 2021 -> 24 (1/2) June 2021" }],
        },
        {
            title: "John Doe",
            pills: [{ title: "Yop", level: 0, colSpan: "02 June 2021 -> 12 (1/2) June 2021" }],
        },
    ]);

    await keyDown("Control");

    // move blop to John Doe
    const { drop, moveTo } = await dragPill("Blop");
    await moveTo({ columnHeader: "14", groupHeader: "June 2021", row: "John Doe" });

    expect(SELECTORS.renderer).toHaveClass("o_copying");

    await drop({ columnHeader: "14", groupHeader: "June 2021", row: "John Doe" });

    expect(getGridContent().rows).toEqual([
        {
            title: "👤 Unassigned",
        },
        {
            title: "Jane Doe",
            pills: [{ title: "Blop", level: 0, colSpan: "14 June 2021 -> 24 (1/2) June 2021" }],
        },
        {
            title: "John Doe",
            pills: [
                { title: "Yop", level: 0, colSpan: "Out of bounds (3)  -> 12 (1/2) June 2021" },
                { title: "Blop (copy)", level: 0, colSpan: "14 June 2021 -> 24 (1/2) June 2021" },
            ],
        },
    ]);
});

test("Smart scheduling", async () => {
    Task._records.push({
        id: 3,
        name: "Gnop",
        user_ids: [100],
    });

    onRpc("schedule_tasks", function (request) {
        expect.step("schedule_tasks");
        return this.env["project.task"].write(...request.args);
    });

    await mountGanttView(ganttViewParams);

    expect(getGridContent().rows).toEqual([
        {
            title: "👤 Unassigned",
        },
        {
            title: "Jane Doe",
            pills: [{ title: "Blop", level: 0, colSpan: "14 June 2021 -> 24 (1/2) June 2021" }],
        },
        {
            title: "John Doe",
            pills: [{ title: "Yop", level: 0, colSpan: "02 June 2021 -> 12 (1/2) June 2021" }],
        },
    ]);

    await clickCell("10", "June 2021", "Jane Doe");
    expect(".o_dialog").toHaveCount(1);
    await contains(".o_dialog .o_data_row .o-checkbox").click();
    await contains(".o_dialog .o_auto_plan_button:enabled").click();
    expect(getGridContent().rows).toEqual([
        {
            title: "👤 Unassigned",
        },
        {
            title: "Jane Doe",
            pills: [
                { title: "Gnop", level: 0, colSpan: "10 June 2021 -> 10 June 2021" },
                { title: "Blop", level: 0, colSpan: "14 June 2021 -> 24 (1/2) June 2021" },
            ],
        },
        {
            title: "John Doe",
            pills: [{ title: "Yop", level: 0, colSpan: "02 June 2021 -> 12 (1/2) June 2021" }],
        },
    ]);
    expect.verifySteps(["schedule_tasks"]);
});

test("Smart scheduling: display warnings", async () => {
    Task._records.push({
        id: 3,
        name: "Gnop",
        user_ids: [100],
    });

    onRpc("schedule_tasks", () => {
        expect.step("schedule_tasks");
        return [
            {},
            {
                3: {
                    planned_date_begin: false,
                    date_deadline: false,
                },
            },
        ];
    });

    let notifications = [];
    mockService("notification", {
        add: (message, options) => {
            expect.step("notification added");
            expect(options["type"]).toBe("success");
            expect(options["buttons"].length).toBe(1);
            expect(options["buttons"][0].icon).toBe("fa-undo");
            expect(options["buttons"][0].name).toBe("Undo");
            notifications.push({ message, options });
            return () => {
                notifications = notifications.filter(
                    (n) => n.message !== message || n.options !== options
                );
            };
        },
    });

    const ganttView = await mountGanttView(ganttViewParams);

    await clickCell("10", "June 2021", "Jane Doe");
    expect(".o_dialog").toHaveCount(1);
    await contains(".o_dialog .o_data_row .o-checkbox").click();
    await contains(".o_dialog .o_auto_plan_button:enabled").click();
    expect.verifySteps(["schedule_tasks", "notification added"]);
    expect(notifications).toHaveLength(1);
    destroy(ganttView);
    expect(notifications).toHaveLength(0);
});

test("Schedule a task and verify its display in the gantt view", async () => {
    Task._records.push({
        id: 3,
        name: "Gnop",
        user_ids: [100],
    });

    onRpc("web_gantt_write", ({ args }) => {
        expect.step("web_gantt_write");
        expect(args[0]).toEqual([3], { message: "should write on the correct record" });
        expect(args[1]).toEqual(
            {
                planned_date_begin: "2021-06-09 23:00:00",
                date_deadline: "2021-06-10 23:00:00",
                user_ids: [100],
            },
            { message: "should write these changes" }
        );
    });

    await mountGanttView(ganttViewParams);

    expect(getGridContent().rows).toEqual([
        {
            title: "👤 Unassigned",
        },
        {
            title: "Jane Doe",
            pills: [{ title: "Blop", level: 0, colSpan: "14 June 2021 -> 24 (1/2) June 2021" }],
        },
        {
            title: "John Doe",
            pills: [{ title: "Yop", level: 0, colSpan: "02 June 2021 -> 12 (1/2) June 2021" }],
        },
    ]);

    await clickCell("10", "June 2021", "Jane Doe");
    expect(".o_dialog").toHaveCount(1);
    await contains(".o_dialog .o_data_row .o-checkbox input").check();
    await clickModalButton({ text: "Select" });
    expect(getGridContent().rows).toEqual([
        {
            title: "👤 Unassigned",
        },
        {
            title: "Jane Doe",
            pills: [
                { title: "Gnop", level: 0, colSpan: "10 June 2021 -> 10 June 2021" },
                { title: "Blop", level: 0, colSpan: "14 June 2021 -> 24 (1/2) June 2021" },
            ],
        },
        {
            title: "John Doe",
            pills: [{ title: "Yop", level: 0, colSpan: "02 June 2021 -> 12 (1/2) June 2021" }],
        },
    ]);
    expect.verifySteps(["web_gantt_write"]);
});

test("Should open the list dialog with 'Open Tasks' filter on Gantt cell click", async () => {
    Task._records.push({ id: 4, name: "Task 4", is_closed: true }, { id: 5, name: "Task 5" });

    await mountGanttView({
        ...ganttViewParams,
        searchViewArch: `
                <search>
                    <filter string="Open Tasks" name="open_tasks" domain="[('is_closed', '=', False)]"/>
                </search>`,
    });

    await clickCell("10", "June 2021", "Jane Doe");
    expect(".o_dialog").toHaveCount(1);
    expect(".o_searchview_facet").toHaveCount(1, { message: "Open Tasks filter applied" });
    expect(".o_data_row").toHaveCount(1, { message: "Only open task should appear" });
});

test("template dropdown in gantt view of a project with no template", async () => {
    await mountGanttView({
        ...ganttViewParams,
        context: {
            default_project_id: 1,
        },
    });
    expect(".o_gantt_button_add").toHaveCount(1, {
        message: "The “New” button should be displayed",
    });
    expect(".o_gantt_button_add").not.toHaveClass("dropdown-toggle", {
        message: "The “New” button should not be a dropdown since there is no template",
    });

    // Test that we can create a new record without errors
    await contains(".o_gantt_button_add").click();
});

test("template dropdown in gantt view of a project with one template", async () => {
    Task._records.push(
        {
            id: 3,
            name: "Template Task 1",
            project_id: 1,
            is_template: true,
            planned_date_begin: "2021-06-02 08:00:00",
            date_deadline: "2021-06-12 08:00:00",
        },
        {
            id: 4,
            name: "Template Task 2",
            project_id: 1,
            is_template: true,
            planned_date_begin: "2021-06-02 08:00:00",
            date_deadline: "2021-06-12 08:00:00",
        }
    );
    await mountGanttView({
        ...ganttViewParams,
        context: {
            default_project_id: 1,
        },
    });
    expect(".o_gantt_button_add").toHaveCount(1, {
        message: "The “New” button should be displayed",
    });
    expect(".o_gantt_button_add").toHaveClass("dropdown-toggle", {
        message: "The “New” button should be a dropdown since there is a template",
    });

    await contains(".o_gantt_button_add").click();
    expect("button.dropdown-item:contains('New Task')").toHaveCount(1, {
        message: "The “New Task” button should be in the dropdown",
    });
    expect("button.dropdown-item:contains('Template Task 1')").toHaveCount(1, {
        message: "There should be a button named after the task template",
    });
});

test("Closed tasks in gantt view have lower opacity than open tasks", async () => {
    Task._records = [{ ...Task._records[0], is_closed: true }];

    await mountGanttView({
        ...ganttViewParams,
        groupBy: ["user_ids"],
    });

    expect(".o_gantt_pill").toHaveClass("opacity-50");
});
