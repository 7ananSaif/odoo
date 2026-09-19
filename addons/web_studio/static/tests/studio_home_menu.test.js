import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import {
    contains,
    MockServer,
    mockService,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { MODES } from "@web_studio/studio_service";
import { defineStudioEnvironment } from "./studio_tests_context";

describe.current.tags("desktop");

defineStudioEnvironment();

test("simple rendering", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    expect(".o_app").toHaveCount(4);
    await contains(".o_web_studio_navbar_item button").click();
    expect(".o_app").toHaveCount(5);

    expect(".o_app[data-menu-xmlid=app_1] .o_app_icon").toHaveAttribute(
        "data-src",
        "/web/static/img/default_icon_app.png"
    );
    expect(".o_app[data-menu-xmlid=app_1] .o_caption").toHaveText("Partners 1");
    expect(".o_app[data-menu-xmlid=app_1] .o_web_studio_edit_icon i").toHaveCount(1);

    expect(".o_app[data-menu-xmlid=app_2] .o_app_icon").toHaveStyle({
        backgroundColor: "rgb(198, 87, 42)",
    });
    expect(".o_app[data-menu-xmlid=app_2] i.fa.fa-diamond").toHaveStyle({
        color: "rgb(255, 255, 255)",
    });
    expect(".o_app[data-menu-xmlid=app_2] .o_web_studio_edit_icon i").toHaveCount(1);

    expect(".o_web_studio_new_app .o_app_icon").toHaveAttribute(
        "data-src",
        "/web_studio/static/src/img/default_icon_app.png"
    );
    expect(".o_web_studio_new_app .o_caption").toHaveText("New App");
});

test("Click on a normal App", async () => {
    mockService("studio", {
        open(...args) {
            expect.step("studio:open: " + args);
            super.open(...arguments);
        },
    });

    mockService("menu", {
        setCurrentMenu(menu) {
            expect.step("menu:setCurrentMenu: " + menu.id);
            super.setCurrentMenu(...arguments);
        },
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();
    await contains(".o_web_studio_navbar_item button").click();
    await contains(".o_app[data-menu-xmlid=app_1]").click();

    expect.verifySteps([
        "studio:open: ",
        `studio:open: ${MODES.EDITOR},1`,
        "menu:setCurrentMenu: 1",
    ]);
});

test("Click on new App", async () => {
    mockService("studio", {
        setParams(...args) {
            expect.step(args);
            super.setParams(...arguments);
        },
    });

    mockService("menu", {
        setCurrentMenu(menu) {
            expect.step("menu:setCurrentMenu: " + menu.id);
            super.setCurrentMenu(...arguments);
        },
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();
    await contains(".o_web_studio_navbar_item button").click();
    await contains(".o_web_studio_new_app").click();

    expect.verifySteps([
        [
            {
                mode: MODES.APP_CREATOR,
            },
        ],
    ]);
});

test("Click on edit icon button", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();
    await contains(".o_web_studio_navbar_item button").click();

    // TODO: Check why hover doesn't work
    // expect(".o_app[data-menu-xmlid=app_1] .o_web_studio_edit_icon:visible").toHaveCount(0);
    // await contains(".o_app[data-menu-xmlid=app_1]").hover();
    // expect(".o_app[data-menu-xmlid=app_1] .o_web_studio_edit_icon:visible").toHaveCount(1);
    await contains(".o_app[data-menu-xmlid=app_1] .o_web_studio_edit_icon", {
        visible: false,
    }).click();

    expect(".o_dialog").toHaveCount(1);
    expect(".o_dialog header.modal-header").toHaveText("Edit Application Icon");
    expect(
        ".o_dialog .modal-content.o_web_studio_edit_menu_icon_modal .o_web_studio_icon_creator"
    ).toHaveCount(1);
    expect(".o_dialog footer button").toHaveCount(2);
    expect(".o_dialog footer .btn-primary").toHaveText("Confirm");
    expect(".o_dialog footer .btn-secondary").toHaveText("Cancel");
    await contains(".o_dialog footer .btn-secondary").click();

    expect(".o_dialog").toHaveCount(0);

    await contains(".o_app[data-menu-xmlid=app_1] .o_web_studio_edit_icon", {
        visible: false,
    }).click();
    await contains(".o_dialog footer .btn-primary").click();
    expect(".o_dialog").toHaveCount(0);
});

test("edit an icon", async () => {
    onRpc("/web_studio/edit_menu_icon", async (request) => {
        const { params } = await request.json();
        expect.step("edit_menu_icon");
        expect(params).toEqual({
            context: {
                allowed_company_ids: [1],
                lang: "en",
                tz: "taht",
                uid: 7,
            },
            icon: ["fa fa-leaf", "#00CEB3", "#FFFFFF"],
            menu_id: 1,
        });
        MockServer.current.menus[0].webIcon = params.icon.join(",");
        return true;
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_web_studio_navbar_item button").click();
    await contains(".o_app[data-menu-xmlid=app_1] .o_web_studio_edit_icon", {
        visible: false,
    }).click();
    await contains(".o_web_studio_upload > a").click();

    expect(".o_web_studio_icon .o_app_icon i.fa-leaf").toHaveCount(0);
    await contains(".o_web_studio_selector_icon > button").click();
    await contains(".o_font_awesome_icon_selector_value.fa.fa-leaf").click();
    expect(".o_web_studio_icon .o_app_icon i.fa-leaf").toHaveCount(1);
    await contains(".o_dialog footer .btn-primary").click();

    expect.verifySteps(["edit_menu_icon"]);
    expect(".o_app[data-menu-xmlid=app_1] .o_app_icon i.fa.fa-leaf").toHaveCount(1);
    await contains(".o_web_studio_leave").click();
    await animationFrame();
    expect(".o_app[data-menu-xmlid=app_1] .o_app_icon i.fa.fa-leaf").toHaveCount(1);
});
