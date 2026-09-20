import { beforeEach, expect, test } from "@odoo/hoot";
import {
    contains,
    defineMenus,
    getService,
    mockService,
    mountWithCleanup,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { queryAll } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";

import { methods as mobileNativeMethods } from "@web_mobile/js/services/core";
import { config as transitionConfig } from "@web/core/transition";
import { WebClient } from "@web/webclient/webclient";

beforeEach(async () => patchWithCleanup(transitionConfig, { disabled: true }));

test.tags("mobile");
test("can execute the callback of addHomeShortcut on an App", async () => {
    const MY_IMAGE =
        "iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==";
    patchWithCleanup(mobileNativeMethods, {
        addHomeShortcut({ title, shortcut_url, web_icon }) {
            expect.step("should call addHomeShortcut");
            expect(document.title).toBe(title);
            expect(document.URL).toBe(shortcut_url);
            expect(web_icon).toBe(MY_IMAGE);
        },
    });
    defineMenus([
        {
            id: 2,
            children: [],
            name: "App2",
            appID: 2,
            actionID: 1003,
            xmlid: "menu_2",
            webIconData: `data:image/png;base64,${MY_IMAGE}`,
            webIcon: false,
        },
    ]);
    await mountWithCleanup(WebClient);
    getService("menu").setCurrentMenu(2);
    await animationFrame();
    expect(".o_user_menu").toHaveClass("d-none");
    await contains("button.o_mobile_menu_toggle").click();
    await contains(".o_user_menu_mobile > *:contains('Add to Home Screen')", {
        root: document.body,
    }).click();
    expect.verifySteps(["should call addHomeShortcut"]);
});

test.tags("mobile");
test("can execute the callback of addHomeShortcut on the HomeMenu", async () => {
    patchWithCleanup(mobileNativeMethods, {
        addHomeShortcut() {
            expect.step("shouldn't call addHomeShortcut");
        },
    });
    mockService("notification", {
        add(message) {
            expect.step(`notification (${message})`);
        },
    });
    await mountWithCleanup(WebClient);
    await contains("button.o_mobile_menu_toggle").click();
    await contains(".o_user_menu_mobile > *:contains('Add to Home Screen')", {
        root: document.body,
    }).click();
    expect.verifySteps(["notification (No shortcut for Home Menu)"]);
});

test.tags("mobile");
test("can execute the callback of switchAccount", async () => {
    patchWithCleanup(mobileNativeMethods, {
        switchAccount() {
            expect.step("should call switchAccount");
        },
    });
    await mountWithCleanup(WebClient);
    await contains("button.o_mobile_menu_toggle").click();
    expect(
        queryAll(".o_user_menu_mobile > *:contains('My Odoo.com account')", {
            root: document.body,
        })
    ).toHaveCount(0);
    expect(
        queryAll(".o_user_menu_mobile > *:contains('Log out')", {
            root: document.body,
        })
    ).toHaveCount(0);
    await contains(".o_user_menu_mobile > *:contains('Switch/Add Account')", {
        root: document.body,
    }).click();
    expect.verifySteps(["should call switchAccount"]);
});
