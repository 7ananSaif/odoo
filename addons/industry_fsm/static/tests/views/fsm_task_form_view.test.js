import { expect, test } from "@odoo/hoot";
import { queryAllTexts } from "@odoo/hoot-dom";

import { contains, mountView, fields, onRpc } from "@web/../tests/web_test_helpers";

import { defineProjectModels, ProjectProject, ProjectTask } from "@project/../tests/project_models";

defineProjectModels();

test("FSM project.task (form) shows template action in multiple FSM projects", async () => {
    onRpc("has_group", () => true);

    Object.assign(ProjectProject._fields, {
        is_fsm: fields.Boolean({ string: "FSM" }),
    });

    Object.assign(ProjectTask._fields, {
        is_fsm: fields.Boolean({ string: "FSM" }),
    });

    ProjectProject._records = [
        { id: 1, name: "FSM Project Template", is_fsm: true, is_template: true },
        { id: 2, name: "FSM Project Template1", is_fsm: true, is_template: true },
    ];

    ProjectTask._records = [
        { id: 1, is_fsm: true, is_template: true, name: "FSM Task Template1", project_id: 1 },
        { id: 2, is_fsm: true, is_template: true, name: "FSM Task Template2", project_id: 2 },
    ];

    await mountView({
        resModel: "project.task",
        type: "form",
        arch: `
            <form js_class="project_task_form">
              <field name="name"/>
            </form>
        `,
        context: { fsm_mode: true },
    });

    await contains(".o_form_button_create").click();
    expect(queryAllTexts(".o-task-template")).toEqual(["FSM Task Template1", "FSM Task Template2"]);
});
