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
import { onRpc, serverState } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

// TODO: fix this test
test.skip("Scrolling to bottom loads more recent calls", async () => {
    const pyEnv = await startServer();
    let rpcCount = 0;
    onRpc("voip.call", "get_recent_phone_calls", () => {
        ++rpcCount;
    });
    await start();
    for (let i = 0; i < 30; ++i) {
        pyEnv["voip.call"].create({
            phone_number: "(501) 884-5252",
            state: "terminated",
            user_id: serverState.userId,
        });
    }
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Recent')");
    await contains(".o-voip-TabEntry", { count: 13 });
    expect(rpcCount).toBe(1);
    await scroll(".o-voip-History div.overflow-auto", "bottom");
    await contains(".o-voip-TabEntry", { count: 26 });
    expect(rpcCount).toBe(2);
});

test("Recent search term should be taken into account", async () => {
    const searchTerm = "Bob";
    onRpc("voip.call", "get_recent_phone_calls", (args) => {
        if (args.kwargs.search_terms === searchTerm) {
            expect.step("get_recent_phone_calls called with search term");
        }
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button span:contains('Recent')");
    await runAllTimers();
    await insertText("input[id='o-voip-Tab-searchInput']", searchTerm);
    await runAllTimers();
    expect.verifySteps(["get_recent_phone_calls called with search term"]);
    await click("button span:contains('Contacts')");
    await contains("button.active span:contains('Contacts')");
    await click("button span:contains('Recent')");
    await runAllTimers();
    expect.verifySteps(["get_recent_phone_calls called with search term"]);
});
