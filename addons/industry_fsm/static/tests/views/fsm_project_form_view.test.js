import { expect, test } from "@odoo/hoot";

import { contains, mountView, fields, onRpc } from "@web/../tests/web_test_helpers";

import { defineProjectModels, ProjectProject } from "@project/../tests/project_models";

defineProjectModels();

test("fsm project.project (form) show template action", async () => {
    onRpc("has_group", () => true);
    Object.assign(ProjectProject._fields, {
        is_fsm: fields.Boolean({ string: "FSM" }),
    });

    ProjectProject._records = [
        {
            id: 1,
            name: "Fsm Project Template",
            is_fsm: true,
            is_template: true,
        },
        {
            id: 2,
            name: "Test Project Template",
            is_template: true,
        },
    ];

    await mountView({
        resModel: "project.project",
        type: "form",
        arch: `
            <form js_class="project_project_form">
                <field name="active"/>
                <field name="name"/>
            </form>
        `,
        context: { fsm_mode: true },
    });

    await contains(".o_form_button_create").click();

    expect("button.dropdown-item:contains('Fsm Project Template')").toHaveCount(1, {
        message: "Only FSM project templates should be shown in the dropdown.",
    });
    expect("button.dropdown-item:contains('Test Project Template')").toHaveCount(0, {
        message: "Non-FSM project templates should not be shown in the dropdown.."
    });
 
});
