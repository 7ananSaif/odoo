import { describe, expect, test } from "@odoo/hoot";
import { queryAll, queryFirst } from "@odoo/hoot-dom";
import { fields, mountView } from "@web/../tests/web_test_helpers";
import { mailModels } from "@mail/../tests/mail_test_helpers";
import { defineProjectModels, projectModels } from "@project/../tests/project_models";

describe.current.tags("desktop");
defineProjectModels();

test("Test muted label for unplanned task in map", async () => {
    Object.assign(mailModels.ResPartner._fields, {
        partner_latitude: fields.Float({ string: "Latitude" }),
        partner_longitude: fields.Float({ string: "Longitude" }),
        contact_address_complete: fields.Char({ string: "Complete Address" }),
    });

    mailModels.ResPartner._records.push({
        id: 103,
        name: "Foo",
        partner_latitude: 10.0,
        partner_longitude: 10.5,
        contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
    });

    projectModels.ProjectTask._records = [
        { id: 1, name: "Unscheduled task", partner_id: 103 },
        {
            id: 2,
            name: "Scheduled task",
            partner_id: 103,
            planned_date_begin: "2023-10-18 06:30:12",
        },
    ];

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `
            <map res_partner="partner_id" routing="1" js_class="project_task_map">
                <field name="partner_id" string="Customer"/>
                <field name="planned_date_begin" string="Date"/>
            </map>`,
    });

    expect(queryFirst(".o-map-renderer--pin-list-details li")).toHaveClass("text-muted", {
        message: "text should be greyed out",
    });
    expect(queryFirst(".o-map-renderer--pin-list-details li")).toHaveText("1. Unscheduled task", {
        message: "The name of the unscheduled task should be muted",
    });

    // Selector for the second-to-last list item (the second cell)
    expect(queryAll(".o-map-renderer--pin-list-details li")[1]).not.toHaveClass("text-muted", {
        message: "text should not be greyed out",
    });
    expect(queryAll(".o-map-renderer--pin-list-details li")[1]).toHaveText("2. Scheduled task", {
        message: "The name of the scheduled task shouldn't be muted",
    });
});
