import {
    click,
    contains,
    insertText,
    scroll,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { expect, describe, test } from "@odoo/hoot";
import { runAllTimers } from "@odoo/hoot-mock";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { onRpc } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("Partners with a phone number are displayed in Contacts tab", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "Michel Landline", phone: "+1-307-555-0120" },
        { name: "Patrice Nomo" },
    ]);
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Contacts')");
    await contains(".o-voip-TabEntry", { count: 1 });
    await contains(".o-voip-TabEntry span", { text: "Michel Landline" });
    await contains(".o-voip-TabEntry span", { text: "Patrice Nomo", count: 0 });
});

test("Typing in the search bar fetches and displays the matching contacts", async () => {
    const pyEnv = await startServer();
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Contacts')");
    pyEnv["res.partner"].create([
        { name: "Morshu RTX", phone: "+61-855-527-77" },
        { name: "Gargamel", phone: "+61-855-583-671" },
    ]);
    await insertText("input[id='o-voip-Tab-searchInput']", "Morshu");
    await contains(".o-voip-TabEntry span", { text: "Morshu RTX" });
    await contains(".o-voip-TabEntry span", { text: "Gargamel", count: 0 });
});

test("Scrolling to bottom loads more contacts", async () => {
    const pyEnv = await startServer();
    let rpcCount = 0;
    onRpc("res.partner", "get_contacts", () => {
        ++rpcCount;
    });
    await start();
    for (let i = 0; i < 10; ++i) {
        pyEnv["res.partner"].create({ name: `Contact ${i}`, phone: `09225 982 ext. ${i}` });
    }
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Contacts')");
    await contains(".o-voip-TabEntry", { count: 10 });
    expect(rpcCount).toBe(1);
    for (let i = 0; i < 10; ++i) {
        pyEnv["res.partner"].create({ name: `Contact ${i + 10}`, phone: `040 2805 ext. ${i}` });
    }
    await contains(".o-voip-TabEntry", { count: 10 });
    await scroll(".o-voip-AddressBook div.overflow-auto", "bottom");
    await contains(".o-voip-TabEntry", { count: 20 });
    expect(rpcCount).toBe(2);
});

test("Contacts with are listed under the their corresponding section", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "", phone: "+1-555-0001" }, // Contact with empty name
        { name: false, phone: "+1-555-0002" }, // Contact with false name
        { name: "Alice", phone: "+1-555-0003" }, // Normal contact
    ]);
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Contacts')");
    await contains(".o-voip-TabEntry", { count: 3 });
    await contains(".o-voip-TabEntry span", {
        text: "Alice",
        parent: ["section", { contains: [["h2", { text: "A" }]] }],
    });
    await contains(".o-voip-TabEntry span", {
        text: "",
        count: 2,
        parent: ["section", { contains: [["h2", { text: "#" }]] }],
    });
});

test("Contact search term should be taken into account", async () => {
    const searchTerm = "Bob";
    onRpc("res.partner", "get_contacts", (args) => {
        if (args.kwargs.search_terms === searchTerm) {
            expect.step("get_contacts called with search term");
        }
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Contacts')");
    await runAllTimers();
    await insertText("input[id='o-voip-Tab-searchInput']", searchTerm);
    await runAllTimers();
    expect.verifySteps(["get_contacts called with search term"]);
    await click("button span:contains('Recent')");
    await contains("button.active span:contains('Recent')");
    await click("button span:contains('Contacts')");
    await runAllTimers();
    expect.verifySteps(["get_contacts called with search term"]);
});
