import { describe, expect, test } from "@odoo/hoot";
import { edit } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    contains,
    MockServer,
    mountWithCleanup,
    onRpc,
    sortableDrag,
    stepAllNetworkCalls,
} from "@web/../tests/web_test_helpers";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { defineStudioEnvironment } from "./studio_tests_context";

describe.current.tags("desktop");

defineStudioEnvironment();

test("edit menu behavior", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_web_studio_navbar_item button").click();
    await contains(".o_app[data-menu-xmlid=app_1]").click();
    expect(".o-web-studio-appmenu-editor").toHaveCount(0);
    await contains(".o_web_edit_menu").click();
    expect(".o-web-studio-appmenu-editor").toHaveCount(1);
});

test("edit menu dialog rendering", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_web_studio_navbar_item button").click();
    await contains(".o_app[data-menu-xmlid=app_1]").click();
    await contains(".o_web_edit_menu").click();

    expect("ul.oe_menu_editor > li").toHaveAttribute("data-item-id", "1");
    expect(
        "ul.oe_menu_editor > li > div button.o-web-studio-interactive-list-edit-item"
    ).toHaveCount(1);
    expect(
        "ul.oe_menu_editor > li > div button.o-web-studio-interactive-list-remove-item"
    ).toHaveCount(1);
    expect("ul.oe_menu_editor > li > ul > li").toHaveCount(2);
    expect(".js_add_menu").toHaveCount(1);
    expect(".o-web-studio-interactive-list-remove-item.disabled").toHaveCount(1);
});

test("edit menu dialog: create menu", async () => {
    expect.assertions(10);

    onRpc("/web_studio/create_new_menu", async (request) => {
        const { params } = await request.json();
        expect(params.menu_name).toBe("AA");
        expect(params.model_choice).toBe("new");
        expect(params.model_options).toEqual(["use_sequence", "use_mail", "use_active"]);
        expect(params.parent_menu_id).toBe(1);
        return {};
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_web_studio_navbar_item button").click();
    await contains(".o_app[data-menu-xmlid=app_1]").click();
    await contains(".o_web_edit_menu").click();

    stepAllNetworkCalls();

    await contains(".js_add_menu").click();
    expect(".o_web_studio_add_menu_modal input[name='menuName']").toHaveCount(1);
    expect(".o_web_studio_add_menu_modal .o_record_selector").toHaveCount(0);

    await edit("new_model");
    await contains(".o_web_studio_add_menu_modal .btn-primary").click();
    expect(".o_web_studio_model_configurator input[name='use_partner']").toHaveCount(1);

    await contains(
        ".o_web_studio_model_configurator .o_web_studio_model_configurator_previous"
    ).click();
    expect(".o_web_studio_model_configurator").toHaveCount(0);

    await contains(
        ".o_web_studio_add_menu_modal .o_web_studio_menu_creator_model_choice [value='existing']"
    ).click();
    expect(".o_web_studio_add_menu_modal .o_record_selector").toHaveCount(1);

    await contains(".o_web_studio_add_menu_modal input[name='menuName']").click();
    await edit("AA");
    await animationFrame();

    await contains(
        ".o_web_studio_add_menu_modal .o_web_studio_menu_creator_model_choice [value='new']"
    ).click();
    await contains(".o_web_studio_add_menu_modal .btn-primary").click();
    await contains(".o_web_studio_model_configurator .btn-primary").click();

    expect.verifySteps(["/web_studio/create_new_menu", "/web/webclient/load_menus"]);
});

test("drag/drop to reorganize menus", async () => {
    expect.assertions(3);

    onRpc("ir.ui.menu", "customize", ({ kwargs }) => {
        expect(kwargs.to_delete).toEqual([]);
        expect(kwargs.to_move).toEqual({
            11: {
                sequence: 2,
            },
            12: {
                parent_menu_id: 1,
                sequence: 1,
            },
        });

        return true;
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_web_studio_navbar_item button").click();
    await contains(".o_app[data-menu-xmlid=app_1]").click();
    await contains(".o_web_edit_menu").click();

    stepAllNetworkCalls();

    const { moveAbove, drop } = await sortableDrag("li[data-item-id='12'] .o-draggable-handle");
    await moveAbove("li[data-item-id='11'] .o-draggable-handle");
    await drop();
    await animationFrame();
    await contains(".o-web-studio-appmenu-editor footer .btn-primary").click();
    expect.verifySteps(["customize", "/web/webclient/load_menus"]);
});

test("edit/delete menus", async () => {
    expect.assertions(12);

    onRpc("ir.ui.menu", "customize", ({ kwargs }) => {
        expect(kwargs.to_delete).toEqual([12]);
        return true;
    });

    onRpc("ir.ui.menu", "web_save", ({ args }) => {
        expect(args[0]).toEqual([1]);
        expect(args[1]).toEqual({ name: "New Partner Menu 1" });
        const { menus } = MockServer.current;
        menus.find((m) => m.id === args[0][0]).name = args[1].name;
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_web_studio_navbar_item button").click();
    await contains(".o_app[data-menu-xmlid=app_1]").click();
    await contains(".o_web_edit_menu").click();
    expect(".o-web-studio-interactive-list-item-label").toHaveCount(3);

    stepAllNetworkCalls();
    await contains(".o-web-studio-interactive-list-edit-item").click();
    expect(".o_dialog").toHaveCount(2);
    expect(".o_dialog .o_form_view").toHaveCount(1);
    expect.verifySteps(["get_views", "web_read"]);

    await edit("New Partner Menu 1");
    await contains(".o_form_button_save").click();
    expect(".o_dialog").toHaveCount(1);
    expect(".o-web-studio-interactive-list-item-label:eq(0)").toHaveText("New Partner Menu 1");
    expect.verifySteps(["web_save", "/web/webclient/load_menus"]);

    await contains(".o-web-studio-interactive-list-remove-item:eq(2)").click();
    expect(".o-web-studio-interactive-list-item-label").toHaveCount(2);
    await contains(".modal footer .btn-primary").click();
    expect.verifySteps(["customize", "/web/webclient/load_menus"]);
});
