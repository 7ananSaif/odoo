import { describe, test } from "@odoo/hoot";
import { advanceTime } from "@odoo/hoot-mock";
import {
    click,
    contains,
    insertText,
    start,
    startServer,
    triggerHotkey,
} from "@mail/../tests/mail_test_helpers";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { serverState } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("Clicking on close button closes the softphone.", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-Softphone");
    await click(".o-voip-Softphone button[title='Hide']");
    await contains(".o-voip-Softphone", { count: 0 });
});

test.tags("focus required");
test("Search bar is focused after switching to a tab with search bar.", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Keypad')");
    await contains(".o-voip-Dialer input:focus");
    await click("button span:contains('Recent')");
    await contains("input[placeholder='Search…']:focus");
});

test.tags("focus required");
test("Search bar is focused after reopen the softphone.", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Keypad')");
    await contains(".o-voip-Dialer input:focus");
    await click(".o-voip-Softphone button[title='Hide']");
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-Dialer input:focus");
    await click("button span:contains('Recent')");
    await click(".o-voip-Softphone button[title='Hide']");
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains("input[placeholder='Search…']:focus");
});

test("Clicking on a tab makes it the active tab.", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains("button.active span:contains('Keypad')");
    await contains("button.active span:contains('Recent')", { count: 0 });
    await click("button span:contains('Recent')");
    await contains("button.active span:contains('Recent')");
});

test("Using VoIP in prod mode without configuring the server shows an error", async () => {
    const pyEnv = await startServer();
    const providerId = pyEnv["voip.provider"].create({
        mode: "prod",
        name: "Axivox super cool",
        pbx_ip: "",
        ws_server: "",
    });
    pyEnv["res.users"].write([serverState.userId], { voip_provider_id: providerId });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-ErrorScreen");
});

test.tags("focus required");
test("When a call is created, a partner with a corresponding phone number is displayed", async () => {
    const pyEnv = await startServer();
    const phoneNumber = "0456 703 6196";
    pyEnv["res.partner"].create({ name: "Maxime Randonnées", phone: phoneNumber });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    // dropdown requires an extra delay before click (because handler is registered in useEffect)
    await contains("button span:contains('Keypad')");
    await click("button span:contains('Keypad')");
    // ensure initial focusing is done before inserting text to avoid focus reset
    await contains(".o-voip-Dialer input:focus");
    await insertText(".o-voip-Dialer input:focus", phoneNumber);
    await triggerHotkey("Enter");
    await advanceTime(5000);
    await contains(".o-voip-InCallView", { text: "Maxime Randonnées" });
});

test("The softphone top bar indicates 'Demo Mode' in demo mode.", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-Softphone header:contains(Demo Mode)");
});
