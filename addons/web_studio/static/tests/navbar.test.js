import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime, queryAllTexts, resize, waitFor } from "@odoo/hoot-dom";
import { animationFrame, Deferred } from "@odoo/hoot-mock";
import { EventBus } from "@odoo/owl";
import {
    contains,
    defineMenus,
    getService,
    makeMockEnv,
    MockServer,
    mockService,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { AppMenuEditor } from "@web_studio/client_action/editor/app_menu_editor/app_menu_editor";
import { NewModelItem } from "@web_studio/client_action/editor/new_model_item/new_model_item";
import { StudioNavbar } from "@web_studio/client_action/navbar/navbar";
import { defineStudioEnvironment } from "./studio_tests_context";

describe.current.tags("desktop");

const extraMenus = [
    {
        id: 100,
        name: "The chain (the song)",
        appID: 1,
        xmlid: "menu_100",
    },
    {
        id: 101,
        name: "Running in the shadows, damn your love, damn your lies",
        appID: 1,
        xmlid: "menu_101",
    },
    {
        id: 102,
        name: "You would never break the chain (Never break the chain)",
        appID: 1,
        xmlid: "menu_102",
    },
    {
        id: 103,
        name: "Chain keep us together (running in the shadow)",
        appID: 1,
        xmlid: "menu_103",
    },
];

test("menu buttons will not be placed under 'more' menu", async () => {
    defineMailModels();
    const menus = [
        {
            id: 1,
            children: [
                { id: 10, children: [], name: "Section 10", appID: 1 },
                { id: 11, children: [], name: "Section 11", appID: 1 },
                {
                    id: 12,
                    children: [
                        { id: 120, children: [], name: "Section 120", appID: 1 },
                        { id: 121, children: [], name: "Section 121", appID: 1 },
                        { id: 122, children: [], name: "Section 122", appID: 1 },
                    ],
                    name: "Section 12",
                    appID: 1,
                },
            ],
            name: "App0",
            appID: 1,
        },
    ];

    defineMenus(menus);

    class MyStudioNavbar extends StudioNavbar {
        async adapt() {
            const prom = super.adapt();
            const sectionsCount = this.currentAppSections.length;
            const hiddenSectionsCount = this.currentAppSectionsExtra.length;
            expect.step(`adapt -> hide ${hiddenSectionsCount}/${sectionsCount} sections`);
            return prom;
        }
    }

    mockService("studio", {
        get mode() {
            // Will force the the navbar in the studio editor state
            return "editor";
        },
    });
    mockService("ui", (env) => {
        Object.defineProperty(env, "isSmall", {
            value: false,
        });
        return {
            bus: new EventBus(),
            size: 0,
            isSmall: false,
        };
    });

    const env = await makeMockEnv();

    const menuButtonsRegistry = registry.category("studio_navbar_menubuttons");
    menuButtonsRegistry.add(
        "app_menu_editor",
        {
            Component: AppMenuEditor,
            props: { env },
        },
        { force: true }
    );
    menuButtonsRegistry.add("new_model_item", { Component: NewModelItem }, { force: true });

    await getService("menu").setCurrentMenu(1);

    await mountWithCleanup(MyStudioNavbar);
    await animationFrame();

    expect(".o_menu_sections > *:not(.o_menu_sections_more):not(.d-none)").toHaveCount(3);
    expect(".o_menu_sections_more").toHaveCount(0);
    expect(".o-studio--menu > *").toHaveCount(2);
    expect(queryAllTexts(".o-studio--menu > *")).toEqual(["Edit Menu", "New Model"]);

    await resize({
        width: 400,
    });
    await advanceTime(2000);

    expect(".o_menu_sections > *:not(.d-none)").toHaveCount(1);
    expect(".o_menu_sections_more:not(.d-none)").toHaveCount(1);
    expect(".o-studio--menu > *").toHaveCount(2);
    expect(queryAllTexts(".o-studio--menu > *")).toEqual(["Edit Menu", "New Model"]);

    await contains(".o_menu_sections_more .dropdown-toggle").click();
    expect(queryAllTexts(".dropdown-menu > *")).toEqual([
        "Section 10",
        "Section 11",
        "Section 12",
        "Section 120",
        "Section 121",
        "Section 122",
    ]);

    expect.verifySteps(["adapt -> hide 0/3 sections", "adapt -> hide 3/3 sections"]);
});

test("homemenu customizer rendering", async () => {
    defineMailModels();

    mockService("studio", {
        get mode() {
            // Will force the the navbar in the studio home_menu state
            return "home_menu";
        },
    });

    await mountWithCleanup(StudioNavbar);
    await animationFrame();

    expect(".o_studio_navbar").toHaveCount(1);
    expect(".o_web_studio_home_studio_menu").toHaveCount(1);
    expect(".o_web_studio_change_background").toHaveCount(1);
    expect(".o_web_studio_change_background input").toHaveAttribute("accept", "image/*");
    expect(".o_web_studio_import").toHaveCount(1);
    expect(".o_web_studio_export").toHaveCount(1);
});

test("adapt navbar when leaving studio", async () => {
    defineStudioEnvironment();
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();
    await resize({ width: 1120 });
    await animationFrame();

    await contains(".o_app[data-menu-xmlid=app_1]").click();
    await animationFrame();

    expect(".o_menu_sections .o_menu_sections_more").toHaveCount(0);

    await contains(".o_web_studio_navbar_item button").click();

    expect(".o_studio .o_menu_sections").toHaveCount(2);
    expect(".o_studio .o_menu_sections .o_menu_sections_more").toHaveCount(0);

    MockServer.current.menus[0].children.push(...extraMenus);

    await getService("menu").reload();
    await animationFrame();
    await advanceTime(2000);

    expect(".o_studio header .o_menu_sections > *:not(.d-none)").toHaveCount(4);
    expect(".o_studio .o_menu_sections .o_menu_sections_more").toHaveCount(1);

    await contains(".o_web_studio_leave").click();
    await animationFrame();
    await advanceTime(2000);
    expect(".o_studio").toHaveCount(0);
    expect("header .o_menu_sections > *:not(.d-none)").toHaveCount(5);
    expect(".o_menu_sections .o_menu_sections_more").toHaveCount(1);
});

test("concurrency: open studio while loading the views", async () => {
    defineStudioEnvironment();

    const def = new Deferred();
    onRpc("get_views", async () => {
        await def;
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_app[data-menu-xmlid=app_1]").click();
    expect(".o_web_studio_navbar_item.o_disabled").toHaveCount(1);

    await contains(".o_web_studio_navbar_item button").click();
    def.resolve();

    await waitFor(".o_kanban_view");

    expect(".o_web_studio_navbar_item button:not(.o_disabled)").toHaveCount(1);
    expect(".o_web_studio_editor_manager").toHaveCount(0);
});
