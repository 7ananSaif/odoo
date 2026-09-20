import { describe, test } from "@odoo/hoot";

import { click, contains, start, startServer, insertText } from "@mail/../tests/mail_test_helpers";

import { setupVoipTests } from "@voip/../tests/voip_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("clicking contact button opens contact form for existing contacts", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([{ name: "Adel Shakal", phone: "+1-307-555-0120" }]);
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Contacts')");
    await click(".o-voip-TabEntry:contains('Adel Shakal') summary button[title='Call']");
    await contains("button[title='View customer details'] i.oi-user");
    await click("button[title='View customer details']");
    await contains(".o_form_sheet");
    await contains("div[name='name'] input", { value: "Adel Shakal" });
});

test("clicking contact button opens contact form for unknown numbers", async () => {
    const TEST_PHONE_NUMBER = "+1-555-123-4567";
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Keypad')");
    await insertText(".o-voip-Dialer input", TEST_PHONE_NUMBER);
    await click("button[title='Call']");
    await contains("button[title='View customer details'] i.oi-user-plus");
    await click("button[title='View customer details']");
    await contains(".o_form_sheet");
});
