import { click, contains, start, startServer } from "@mail/../tests/mail_test_helpers";
import { onRpc } from "@web/../tests/web_test_helpers";
import { describe, test } from "@odoo/hoot";
import { defineVoipCRMModels } from "@voip_crm/../tests/voip_crm_test_helpers";

describe.current.tags("desktop");
defineVoipCRMModels();

test("LeadButton is hidden when user doesn't have sales team groups", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "Test Partner",
        phone: "+1-555-123-4567",
    });
    onRpc("has_group", () => false);
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Contacts')");
    await click(".o-voip-TabEntry:contains('Test Partner')");
    await contains("button[title='Create a lead']", { count: 0 });
});

test("LeadButton is shown when user has sales team groups", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "Test Partner",
        phone: "+1-555-123-4567",
    });
    onRpc("has_group", (args) => {
        const group = args.args[1];
        return group === "sales_team.group_sale_salesman";
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Contacts')");
    await click(".o-voip-TabEntry:contains('Test Partner')");
    await contains("button[title='Create a lead']");
});

test("LeadButton is shown when user has sales manager group", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "Test Partner",
        phone: "+1-555-123-4567",
    });
    onRpc("has_group", (args) => {
        const group = args.args[1];
        return group === "sales_team.group_sale_manager";
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Contacts')");
    await click(".o-voip-TabEntry:contains('Test Partner')");
    await contains("button[title='Create a lead']");
});

test("LeadButton is shown with title 'View lead' and icon 'fa-star' when user has sales team groups", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "Test Partner",
        phone: "+1-555-123-4567",
        opportunity_count: 1,
    });
    onRpc("has_group", (args) => {
        const group = args.args[1];
        return group === "sales_team.group_sale_salesman";
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Contacts')");
    await click(".o-voip-TabEntry:contains('Test Partner')");
    await contains("button[title='View leads'] i.fa-star");
});

test("LeadButton is shown with title 'View lead' and icon 'fa-star' when user has sales manager groups", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "Test Partner",
        phone: "+1-555-123-4567",
        opportunity_count: 1,
    });
    onRpc("has_group", (args) => {
        const group = args.args[1];
        return group === "sales_team.group_sale_manager";
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Contacts')");
    await click(".o-voip-TabEntry:contains('Test Partner')");
    await contains("button[title='View leads'] i.fa-star");
});
