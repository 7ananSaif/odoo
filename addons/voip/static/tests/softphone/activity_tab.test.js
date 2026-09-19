import { describe, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";
import { click, contains, start, startServer } from "@mail/../tests/mail_test_helpers";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { serverState } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("Call activities are displayed in the “Activities” tab.", async () => {
    mockDate("1993-08-12 12:00:00");
    const pyEnv = await startServer();
    const [activityTypeId] = pyEnv["mail.activity.type"].search([["category", "=", "phonecall"]]);
    const [partnerId1, partnerId2] = pyEnv["res.partner"].create([
        {
            name: "Françoise Délire",
            phone: "+1 246 203 6982",
            company_name: "Boulangerie Vortex",
        },
        {
            name: "Naomi Dag",
            phone: "777 2124",
            company_name: "Sanit’Hair",
        },
    ]);
    pyEnv["mail.activity"].create([
        {
            activity_type_id: activityTypeId,
            date_deadline: "1993-08-12",
            res_id: partnerId1,
            res_model: "res.partner",
            user_id: serverState.userId,
        },
        {
            activity_type_id: activityTypeId,
            date_deadline: "1993-08-11",
            res_id: partnerId2,
            res_model: "res.partner",
            user_id: serverState.userId,
        },
    ]);
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Activities')");
    await contains(".o-voip-TabEntry", { count: 2 });
    await contains("h2.text-danger", {
        text: "Due: Yesterday",
    });
    await contains(".o-voip-TabEntry", {
        text: "Sanit’Hair, Naomi Dag",
    });
    await contains("h2", {
        text: "Due: Today",
    });
    await contains(".o-voip-TabEntry", {
        text: "Boulangerie Vortex, Françoise Délire",
    });
});

test("The name of the partner linked to an activity is displayed in the activity tab.", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({
        name: "Gwendoline Zumba",
        phone: "515-555-0104",
    });
    pyEnv["mail.activity"].create([
        {
            activity_type_id: pyEnv["mail.activity.type"].search([
                ["category", "=", "phonecall"],
            ])[0],
            date_deadline: "2017-08-13",
            res_id: partnerId,
            res_model: "res.partner",
            user_id: serverState.userId,
        },
    ]);
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Activities')");
    await contains("button[title='Open related record']", {
        text: "Gwendoline Zumba",
    });
});
