import { describe, expect, test } from "@odoo/hoot";
import { click, queryAll } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";

import {
    defineActions,
    defineModels,
    fields,
    getService,
    models,
    mountWithCleanup,
    onRpc,
    makeMockServer,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";

import { definePlanningModels } from "./planning_mock_models";

describe.current.tags("desktop");

/* Main Goals of these tests:
- Tests the change made in planning to avatar card preview for resource:
- Roles appear as tags on the card
- Card should be displayed for material resources with at least 2 roles
*/

/* 1. Create data
    4 type of resources will be tested in the widget:
    - material resource with only one role (Continuity testing computer)
        - clicking the icon should not open any popover
    - material resource with two roles (Integration testing computer)
        - clicking the icon should open a card popover with resource name and roles
    - human resource not linked to a user (Marie)
        - a card popover should open including the roles of the employee
    - human resource linked to a user (Pierre)
        - a card popover should open including the roles of the employee
*/

class ResourceTask extends models.Model {
    _name = "resource.task";

    name = fields.Char();
    display_name = fields.Char();
    resource_ids = fields.One2many({ relation: "resource.resource" });

    _views = {
        form: `
            <form string="Tasks">
                <field name="display_name"/>
                <field name="resource_ids" widget="many2many_avatar_resource"/>
            </form>
        `,
    };
}

onRpc("get_avatar_card_data", function ({ args }) {
    const [ids, fields] = args[0];
    return this.env["resource.resource"].read(ids, fields);
});

defineModels([ResourceTask]);
definePlanningModels();
defineActions([
    {
        id: 1,
        name: "Resource Task",
        res_model: "resource.task",
        res_id: 1,
        views: [[false, "form"]],
    },
]);

test("many2many_avatar_resource widget in form view", async () => {
    const { env } = await makeMockServer();
    const [roleId1, roleId2] = env["planning.role"].create([
        {
            name: "Tester",
            color: 1,
        },
        {
            name: "It Specialist",
            color: 2,
        }
    ]);
    const userId = env["res.users"].create({
        name: "Pierre",
        partner_id: 1,
    });
    const [resourceId1, resourceId2, resourceId3, resourceId4] = env["resource.resource"].create([
        {
            name: "Continuity testing computer",
            resource_type: "material",
            role_ids: [roleId1],
        },
        {
            name: "Integration testing computer",
            resource_type: "material",
            role_ids: [roleId1, roleId2],
        },
        {
            name: "Marie",
            resource_type: "user",
            role_ids: [roleId1],
        },
        {
            name: "Pierre",
            resource_type: "user",
            role_ids: [roleId2],
            im_status: "online",
            user_id: userId,
        },
    ]);
    env["hr.employee"].create([
        {
            name: "Marie",
            resource_id: resourceId3,
        },
        {
            name: "Pierre",
            resource_id: resourceId4,
        },
    ]);

    env["hr.employee"].create([
        {
            name: "Marie",
            resource_id: 3,
        },
        {
            name: "Pierre",
            resource_id: 4,
            user_id: userId,
            user_partner_id: 1,
        },
    ]);

    env["resource.task"].create({
        display_name: "Task with four resources",
        resource_ids: [resourceId1, resourceId2, resourceId3, resourceId4],
    });

    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    expect("img.o_m2m_avatar").toHaveCount(2);
    expect(".fa-wrench").toHaveCount(2);

    // 1. Clicking on material resource's icon with only one role
    await click(".many2many_tags_avatar_field_container .o_tag i.fa-wrench");
    await animationFrame();
    expect(".o_avatar_card").toHaveCount(0);

    // 2. Clicking on material resource's icon with two roles
    await click(queryAll(".many2many_tags_avatar_field_container .o_tag i.fa-wrench")[1]);
    await animationFrame();
    expect(".o_avatar_card").toHaveCount(1);
    expect(".o_avatar_card .o_avatar > img").toHaveCount(0, {
        message: "There should not be any avatar for material resource",
    });
    expect(".o_avatar_card_buttons button").toHaveCount(0);
    expect(".o_avatar_card .o_resource_roles_tags .o_tag").toHaveCount(2, {
        message: "Roles should be listed in the card",
    });

    // 3. Clicking on human resource's avatar with no user associated
    await click(".many2many_tags_avatar_field_container .o_tag img");
    await animationFrame();
    expect(".o_card_user_infos span:first").toHaveText("Marie");
    expect(".o_avatar_card").toHaveCount(1, {
        message: "Only one popover resource card should be opened at a time",
    });

    // 4. Clicking on human resource's avatar with one user associated
    await click(queryAll(".many2many_tags_avatar_field_container .o_tag img")[1]);
    await animationFrame();
    expect(".o_card_user_infos span:first").toHaveText("Pierre");
    expect(".o_avatar_card").toHaveCount(1, {
        message: "Only one popover resource card should be opened at a time",
    });
});
