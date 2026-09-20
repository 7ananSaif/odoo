import { describe, expect, test } from "@odoo/hoot";
import { queryFirst } from "@odoo/hoot-dom";
import { mockTimeZone } from "@odoo/hoot-mock";

import { fields, mountView } from "@web/../tests/web_test_helpers";

import { mailModels } from "@mail/../tests/mail_test_helpers";

import { defineProjectModels, projectModels } from "@project/../tests/project_models";


describe.current.tags("desktop");
defineProjectModels();

test("Fsm task's name and time are displayed correctly in the map view", async () => {
    mockTimeZone(+0);
    Object.assign(mailModels.ResPartner._fields, {
        partner_latitude: fields.Float({ string: "Latitude" }),
        partner_longitude: fields.Float({ string: "Longitude" }),
        contact_address_complete: fields.Char({ string: "Complete Address" }),
    });

    mailModels.ResPartner._records.push({
        id: 103,
        name: "Foo",
        partner_latitude: 23.19002,
        partner_longitude: 72.61682,
        contact_address_complete: "Gandhinagar, 385566, India",
    });

    projectModels.ProjectTask._records = [
        {
            id: 1,
            name: "Scheduled task",
            partner_id: 103,
            planned_date_begin: "2022-02-07 21:00:00",
        },
    ];

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `
            <map res_partner="partner_id" routing="1" js_class="fsm_my_task_map">
                <field name="partner_id" string="Customer"/>
                <field name="planned_date_begin" string="Date"/>
            </map>`,
        context: { fsm_mode: true },
    });

    expect(queryFirst(".o-map-renderer--pin-list-details li")).toHaveText("1. Scheduled task\n21:00", {
        message: "The task name and date of the scheduled task should be displayed correctly with the specified time",
    });
});
