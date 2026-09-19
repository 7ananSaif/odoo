import { expect, test } from "@odoo/hoot";
import {
    defineModels,
    fields,
    patchWithCleanup,
    webModels,
    mountWithCleanup,
} from "@web/../tests/web_test_helpers";
import { mockMatchMedia } from "@odoo/hoot-mock";
import { _makeUser, user } from "@web/core/user";
import { cookie } from "@web/core/browser/cookie";
import { browser } from "@web/core/browser/browser";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { blockingWebClient } from "@web_enterprise/webclient/color_scheme/color_scheme_service";

class ResUsersSettings extends webModels.ResUsersSettings {
    color_scheme = fields.Selection({
        selection: [
            ["system", "System"],
            ["light", "Light"],
            ["dark", "Dark"],
        ],
        default: "system",
    });

    _records = [
        {
            id: 1,
            color_scheme: "system",
        },
    ];
}

defineModels([ResUsersSettings]);

test("use 'system' color scheme (light)", async () => {
    mockMatchMedia({ ["prefers-color-scheme"]: "light" });
    patchWithCleanup(browser.location, {
        reload: () => expect.step("reloadPage"),
    });
    patchWithCleanup(user, _makeUser({ user_settings: { id: 1, color_scheme: "system" } }));
    blockingWebClient.resolve();
    await mountWithCleanup(MainComponentsContainer);
    expect(cookie.get("color_scheme")).toBe("light");
    expect.verifySteps([]);
});

test("use 'system' color scheme (dark)", async () => {
    mockMatchMedia({ ["prefers-color-scheme"]: "dark" });
    patchWithCleanup(browser.location, {
        reload: () => expect.step("reloadPage"),
    });
    patchWithCleanup(user, _makeUser({ user_settings: { id: 1, color_scheme: "system" } }));
    blockingWebClient.resolve();
    await mountWithCleanup(MainComponentsContainer);
    expect(cookie.get("color_scheme")).toBe("dark");
    expect.verifySteps(["reloadPage"]);
});

test("use 'light' color scheme", async () => {
    mockMatchMedia({ ["prefers-color-scheme"]: "dark" });
    patchWithCleanup(browser.location, {
        reload: () => expect.step("reloadPage"),
    });
    patchWithCleanup(user, _makeUser({ user_settings: { id: 1, color_scheme: "light" } }));
    ResUsersSettings._records[0].color_scheme = "light";
    blockingWebClient.resolve();
    await mountWithCleanup(MainComponentsContainer);
    expect(cookie.get("color_scheme")).toBe("light");
    expect.verifySteps([]);
});

test("use 'dark' color scheme", async () => {
    mockMatchMedia({ ["prefers-color-scheme"]: "light" });
    patchWithCleanup(browser.location, {
        reload: () => expect.step("reloadPage"),
    });
    patchWithCleanup(user, _makeUser({ user_settings: { id: 1, color_scheme: "dark" } }));
    ResUsersSettings._records[0].color_scheme = "dark";
    blockingWebClient.resolve();
    await mountWithCleanup(MainComponentsContainer);
    expect(cookie.get("color_scheme")).toBe("dark");
    expect.verifySteps(["reloadPage"]);
});
