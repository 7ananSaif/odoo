import { describe, expect, test } from "@odoo/hoot";
import { check, queryAll } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";

import { mountView } from "@web/../tests/web_test_helpers";

import { defineHelpdeskModels } from "@helpdesk/../tests/helpdesk_test_helpers";

describe.current.tags("desktop");
defineHelpdeskModels();

const listViewParams = {
    resModel: "helpdesk.ticket",
    type: "list",
    arch: `
        <list multi_edit="1" js_class="helpdesk_ticket_list">
            <field name="name"/>
            <field name="team_id"/>
            <field name="stage_id"/>
        </list>
    `,
}

test("(helpdesk.ticket) list cannot update stage with diffrent teams's ticket", async () => {
    await mountView(listViewParams);

    const [firstRow, secondRow, thirdRow] = queryAll(".o_data_row");
    await check(".o_list_record_selector input", { root: firstRow });
    await check(".o_list_record_selector input", { root: secondRow });
    await animationFrame();
    expect(queryAll("[name=stage_id]")).not.toHaveClass("o_readonly_modifier");

    await check(".o_list_record_selector input", { root: thirdRow });
    await animationFrame();
    expect(queryAll("[name=stage_id]")).toHaveClass("o_readonly_modifier");
});
