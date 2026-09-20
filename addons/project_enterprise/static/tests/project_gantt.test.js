import { beforeEach, describe, test, expect } from "@odoo/hoot";
import { queryAllTexts, click } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";

import { onRpc } from "@web/../tests/web_test_helpers";

import { mailModels } from "@mail/../tests/mail_test_helpers";

import { SELECTORS, mountGanttView } from "@web_gantt/../tests/web_gantt_test_helpers";
import { defineProjectModels, projectModels } from "@project/../tests/project_models";

defineProjectModels();
describe.current.tags("desktop");

beforeEach(() => {
    mailModels.ResUsers._records.push({ id: 103, name: "Jane Doe" });
    projectModels.ProjectProject._records = [
        {
            id: 1,
            name: "Test Project 1",
            date_start: "2019-01-05 06:30:00",
            date: "2019-03-05 06:30:00",
            user_id: 103,
        },
    ];
});

const ganttViewParams = {
    arch: '<gantt js_class="project_gantt" date_start="date_start" date_stop="date" default_group_by="user_id"/>',
    resModel: "project.project",
};

test("user_id grouped: specific empty group added, even if no records", async () => {
    await mountGanttView(ganttViewParams);
    expect(queryAllTexts(".o_gantt_row_headers .o_gantt_row_title")).toEqual(
        ["👤 Unassigned", "Jane Doe"],
        {
            message:
                "'👤 Unassigned' should be the first group, even if no record exist without user_ids",
        }
    );
    expect(".o_gantt_row_headers .o-mail-Avatar").toHaveCount(1);
});

test("should display 'View Tasks' and 'Edit' buttons in the popover footer", async () => {
    await mountGanttView({
        arch: `
            <gantt date_start="date_start" date_stop="date">
                <templates>
                    <div t-name="gantt-popover">
                        <footer replace="0">
                            <button name="action_view_tasks" type="object" string="View Tasks"
                                class="btn btn-sm btn-primary"/>
                        </footer>
                    </div>
                </templates>
            </gantt>
        `,
        resModel: "project.project",
    });

    onRpc(({ model, method, kwargs }) => {
        if (model === "project.project" && method === "get_views") {
            expect(model).toBe("project.project");
            expect(method).toBe("get_views");
            expect(kwargs.views).toEqual([[false, "form"]]);
            expect.step("Edit");
        } else if (model === "project.project" && method === "action_view_tasks") {
            expect.step("view tasks");
            return false;
        }
    });
    expect(SELECTORS.pill).toHaveCount(1);

    await click(SELECTORS.pill);
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover .popover-footer button").toHaveCount(2);
    expect(queryAllTexts(".o_popover .popover-footer button")).toEqual(["Edit", "View Tasks"]);
    await click(".o_popover .popover-footer button:first-child");
    await click(".o_popover .popover-footer button:last-child");
    expect.verifySteps(["Edit", "view tasks"]);
});
