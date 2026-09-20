import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click, hover, queryAll } from "@odoo/hoot-dom";
import { animationFrame, mockDate } from "@odoo/hoot-mock";
import {
    contains,
    fields,
    findComponent,
    getService,
    mountWithCleanup,
    preloadBundle,
    onRpc,
} from "@web/../tests/web_test_helpers";

import {
    CLASSES,
    SELECTORS,
    getPillWrapper,
    clickCell,
} from "@web_gantt/../tests/web_gantt_test_helpers";
import { getConnector } from "@web_gantt/../tests/gantt_dependency_helpers";

import { defineProjectModels, ProjectTask } from "@project/../tests/project_models";

onRpc("get_all_deadlines", () => ({ milestone_id: [], project_id: [] }));

let desiredComponent;

const setupAction = async (context = {}) => {
    await getService("action").doAction({
        name: "project task",
        res_model: "project.task",
        type: "ir.actions.act_window",
        views: [
            [false, "gantt"],
            [false, "list"],
            [false, "kanban"],
            [false, "form"],
        ],
        context,
    });
};

describe.current.tags("desktop");
defineProjectModels();

let ProjectSharingWebClient;
preloadBundle("project_enterprise.project_sharing_unit_tests");

beforeEach(async () => {
    mockDate("2021-06-22 08:00:00");

    Object.assign(ProjectTask._fields, {
        allow_task_dependencies: fields.Boolean({ default: true }),
        display_warning_dependency_in_gantt: fields.Boolean({ default: true }),
        portal_user_names: fields.Char(),
    });

    ProjectTask._records.push(
        {
            id: 4,
            name: "Regular task 4",
            planned_date_begin: "2021-06-14 08:00:00",
            date_deadline: "2021-06-24 08:00:00",
            user_ids: [7],
            project_id: 1,
            stage_id: 1,
        },
        {
            name: "Regular task 5",
            planned_date_begin: "2021-06-14 08:00:00",
            date_deadline: "2021-06-24 08:00:00",
            user_ids: [7],
            project_id: 1,
            depend_on_ids: [4],
            stage_id: 2,
        },
        {
            name: "Regular task 6",
            planned_date_begin: "2021-06-14 08:00:00",
            date_deadline: "2021-06-24 08:00:00",
            user_ids: [7],
            project_id: 1,
            stage_id: 2,
            portal_user_names: "admin",
        }
    );

    ProjectTask._views = {
        form: `
            <form>
                <sheet>
                    <field name="name"/>
                </sheet>
                <chatter/>
            </form>
            `,
        list: `<list><field name="name"/></list>`,
        kanban: `<kanban><t t-name="card"><field name="name"/></t></kanban>`,
        gantt: `<gantt date_start="planned_date_begin" date_stop="date_deadline" js_class="task_sharing_gantt" dependency_field="depend_on_ids">
                    <templates>
                        <t t-name="gantt-popover">
                            <footer replace="0">
                                <button name="action_unschedule_task" type="object" string="Unschedule"
                                    class="btn btn-sm btn-secondary"/>
                            </footer>
                        </t>
                    </templates>
                <field name="portal_user_names"/>
            </gantt>
        `,
        search: `<search></search>`,
    };

    ({ ProjectSharingWebClient } = window.odoo.loader.modules.get(
        "@project/project_sharing/project_sharing"
    ));
    desiredComponent = await mountWithCleanup(ProjectSharingWebClient);
});

test(`Load ProjectSharingWebClient component`, async () => {
    const sharingWebClientComponent = findComponent(
        desiredComponent,
        (c) => c instanceof ProjectSharingWebClient
    );
    expect(sharingWebClientComponent instanceof ProjectSharingWebClient).toBe(true);
});

test("Chatter remains hidden until form view is expanded", async () => {
    await setupAction();
    click(".o_gantt_pill");
    await animationFrame();
    click(".o_popover .popover-footer button", { text: "Edit" });
    expect(".o-mail-ChatterContainer").toHaveCount(0);
    await animationFrame();
    click(".o_expand_button");
    await animationFrame();
    expect(".o-mail-ChatterContainer").toHaveCount(1);
});

test("Unschedule button is displayed", async () => {
    onRpc(({ method, model }) => {
        if (model === "project.task" && method == "action_unschedule_task") {
            expect.step("unschedule task");
            return false;
        }
    });
    await setupAction();
    await contains(".o_gantt_pill").click();
    expect(".btn.btn-sm.btn-secondary").toHaveCount(1);
    expect(".btn.btn-sm.btn-secondary").toHaveText("Unschedule");
    await contains(".btn.btn-sm.btn-secondary").click();
    expect.verifySteps(["unschedule task"]);
});

test("Undraggable pill when grouped by project", async () => {
    await setupAction({ group_by: ["project_id"] });
    expect(SELECTORS.draggable).toHaveCount(0);
});

test("Draggable pill when grouped by stage with Assignees", async () => {
    await setupAction({ group_by: ["stage_id"] });
    await animationFrame();
    await contains(".o_content").scroll({ left: 500 });
    await animationFrame();
    expect(getPillWrapper("Regular task 4")).toHaveClass(CLASSES.draggable);
    expect(getPillWrapper("Regular task 6")).toHaveClass(CLASSES.draggable);
});

test("Prevent opening schedule plan dialog when grouped by fields except stage and tags", async () => {
    await setupAction({ group_by: ["project_id"] });
    await clickCell("10", "June 2021");
    await animationFrame();
    expect(".moda").toHaveCount(0, {
        message: "dialog should not open when grouped by fields other than stage and tags",
    });
});

test("Check connector buttons and connector line", async () => {
    await setupAction();
    await hover(getConnector(1));
    await animationFrame();
    expect(queryAll(SELECTORS.connectorStroke, { root: getConnector(1) })).toHaveCount(1);
    await animationFrame();
    expect(queryAll(SELECTORS.connectorStrokeButton, { root: getConnector(1) })).toHaveCount(0);
});
