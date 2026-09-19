import { waitNotifications } from "@bus/../tests/bus_test_helpers";

import { click, contains, start, startServer } from "@mail/../tests/mail_test_helpers";

import { describe, test } from "@odoo/hoot";
import { advanceTime, mockDate } from "@odoo/hoot-mock";

import { setupVoipTests } from "@voip/../tests/voip_test_helpers";

import { serverState } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("Do not disturb selector show all options", async () => {
    const pyEnv = await startServer();
    // DND Selector only shows up in production mode 💡
    const providerId = pyEnv["voip.provider"].create({ mode: "prod" });
    pyEnv["res.users"].write([serverState.userId], { voip_provider_id: providerId });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");

    // don't click on the dropdown too early: handler may not be registered yet
    await contains(".o-voip-DndSelector-badge[title='Available']");
    await click(".o-voip-DndSelector-badge[title='Available']");
    await click("p", { text: "Do Not Disturb" });
    await contains("button", { text: "For 15 minutes" });
    await contains("button", { text: "For 1 hour" });
    await contains("button", { text: "For 3 hours" });
    await contains("button", { text: "For 8 hours" });
    await contains("button", { text: "For 24 hours" });
    await contains("button", { text: "Until I turn it back on" });
});

test("Do not disturb selector changes state correctly with limited time", async () => {
    mockDate("2025-01-01 01:00:00", +0);
    const pyEnv = await startServer();
    // DND Selector only shows up in production mode 💡
    const providerId = pyEnv["voip.provider"].create({ mode: "prod" });
    pyEnv["res.users"].write([serverState.userId], { voip_provider_id: providerId });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");

    // don't click on the dropdown too early: handler may not be registered yet
    await contains(".o-voip-DndSelector-badge[title='Available']");
    await click(".o-voip-DndSelector-badge[title='Available']");
    await click("p", { text: "Do Not Disturb" });
    await click("button", { text: "For 15 minutes" });
    await waitNotifications(["res.users.settings"]);
    // don't click on the dropdown too early: handler may not be registered yet
    await contains(".o-voip-DndSelector-badge i.text-danger");
    await click(".o-voip-DndSelector-badge i.text-danger");
    await contains("p:contains(Until Jan 1, 2025, 1:15)");
    await advanceTime(14 * 60 * 1000, { blockTimers: true });
    await contains(".o-voip-DndSelector-badge i.text-danger");
    await advanceTime(1 * 60 * 1000, { blockTimers: true });
    await contains(".o-voip-DndSelector-badge i.text-success");
});

test("Do not disturb selector change state correctly with infinite time", async () => {
    const pyEnv = await startServer();
    // DND Selector only shows up in production mode 💡
    const providerId = pyEnv["voip.provider"].create({ mode: "prod" });
    pyEnv["res.users"].write([serverState.userId], { voip_provider_id: providerId });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");

    // don't click on the dropdown too early: handler may not be registered yet
    await contains(".o-voip-DndSelector-badge[title='Available']");
    await click(".o-voip-DndSelector-badge[title='Available']");
    await click("p", { text: "Do Not Disturb" });
    await click("button", { text: "Until I turn it back on" });
    await waitNotifications(["res.users.settings"]);
    // don't click on the dropdown too early: handler may not be registered yet
    await contains(".o-voip-DndSelector-badge i.text-danger");
    await click(".o-voip-DndSelector-badge i.text-danger");
    await contains("p", { text: "Until I turn it back on" });
    await advanceTime(24 * 60 * 60 * 1000, { blockTimers: true });
    // don't click on the dropdown too early: handler may not be registered yet
    await contains(".o-voip-DndSelector-badge i.text-danger");
    await click(".o-voip-DndSelector-badge i.text-danger");
    await click(".o-dropdown-item i.text-success");
    await waitNotifications(["res.users.settings"]);
    await contains(".o-voip-DndSelector-badge i.text-success");
});
