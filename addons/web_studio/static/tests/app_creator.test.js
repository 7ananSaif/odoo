import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, globals, test } from "@odoo/hoot";
import { edit, press, setInputFiles, waitFor } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    contains,
    mockService,
    mountWithCleanup,
    onRpc,
    serverState,
} from "@web/../tests/web_test_helpers";
import { AppCreator } from "@web_studio/client_action/app_creator/app_creator";

const sampleIconUrl =
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z9DwHwAGBQKA3H7sNwAAAABJRU5ErkJggg==";

describe.current.tags("desktop");

defineMailModels();

test("app creator: standard flow with model creation", async () => {
    expect.assertions(27);

    onRpc("/web_studio/create_new_app", async (request) => {
        const { params } = await request.json();
        expect(params.app_name).toBe("Kikou");
        expect(params.menu_name).toBe("Petite Perruche");
        expect(params.model_id).toBe(false);
        expect(params.model_choice).toBe("new");
        expect(params.model_options).toEqual([
            "use_partner",
            "use_sequence",
            "use_mail",
            "use_active",
        ]);
        return true;
    });

    onRpc("ir.attachment", "read", () => [{ datas: sampleIconUrl }]);

    onRpc("/web/binary/upload_attachment", () => {
        expect.step("upload_attachment");
        return [{ id: 666 }];
    });

    mockService("ui", {
        block: () => expect.step("UI blocked"),
        unblock: () => expect.step("UI unblocked"),
    });

    await mountWithCleanup(AppCreator, {
        props: { onNewAppCreated: () => expect.step("new-app-created") },
    });
    await animationFrame();

    expect(".o_web_studio_welcome").toHaveCount(1);
    expect(".o_web_studio_app_creator_previous").toHaveCount(0);
    expect(".o_web_studio_app_creator_next").toHaveClass("is_ready");

    await contains(".o_web_studio_app_creator_next").click();

    expect(".o_web_studio_app_creator_name").toHaveCount(1);
    expect(".o_web_studio_icon_creator .o_web_studio_selectors").toHaveCount(1);
    expect(".o_app_icon").toHaveStyle({ backgroundColor: "rgb(255, 255, 255)" });
    expect(".o_app_icon .fa-home").toHaveStyle({ color: "rgb(0, 206, 179)" });

    await contains(".o_web_studio_selector_background > button").click();

    expect(".o_select_menu_menu").toHaveCount(1);

    await contains(".o_web_studio_selector_color > button").click();

    expect(".o_select_menu_menu").toHaveCount(1);

    await contains(".o_web_studio_selector_icon > button").click();

    await contains(".o_select_menu_item .fa-heart").click();

    expect(".o_app_icon .fa-heart").toHaveCount(1);

    const res = await globals.fetch.call(window, "data:image/png;base64," + sampleIconUrl);
    const blob = await res.blob();
    const file = new File([blob], "default_icon_app.png", { type: "image/png" });

    await contains(".o_web_studio_upload a").click();
    await setInputFiles(file);
    await animationFrame();
    await waitFor(".o_web_studio_uploaded_image");

    expect(".o_web_studio_uploaded_image").toHaveStyle({
        backgroundImage: `url("data:image/png;base64,${sampleIconUrl}")`,
    });
    await contains(".o_web_studio_app_creator_next").click();
    expect(".o_web_studio_field_warning").toHaveCount(1);

    await contains("input[name='appName']").click();
    await edit("Kikou");
    await animationFrame();
    expect(".o_web_studio_field_warning").toHaveCount(0);

    await contains(".o_web_studio_app_creator_next").click();

    expect(".o_web_studio_selectors").toHaveCount(0);
    expect(".o_web_studio_menu_creator_model_choice").toHaveCount(1);

    await contains(".o_web_studio_app_creator_next").click();

    expect(".o_web_studio_field_warning").toHaveCount(1);
    await contains("input[name='menuName']").click();
    await edit("Petite Perruche");
    await animationFrame();

    await contains(".o_web_studio_app_creator_next").click();

    expect(".o_web_studio_model_configurator").toHaveCount(1);
    expect("input[name='use_active']:checked").toHaveCount(1);
    expect("input[name='use_partner']").toHaveCount(1);
    await contains("input[name='use_partner']").click();
    expect("input[name='use_partner']:checked").toHaveCount(1);

    await contains(".o_web_studio_model_configurator_previous").click();
    await contains(".o_web_studio_app_creator_next").click();
    expect("input[name='use_partner']:checked").toHaveCount(0);

    await contains("input[name='use_partner']").click();

    await contains(".o_web_studio_model_configurator_next").click();
    expect.verifySteps(["upload_attachment", "UI blocked", "new-app-created", "UI unblocked"]);
});

test("app creator: has 'lines' options to auto-create a one2many", async () => {
    expect.assertions(7);

    onRpc("/web_studio/create_new_app", async (request) => {
        const { params } = await request.json();
        expect(params.app_name).toBe("testApp");
        expect(params.menu_name).toBe("testMenu");
        expect(params.model_id).toBe(false);
        expect(params.model_choice).toBe("new");
        expect(params.model_options).toEqual(["lines", "use_sequence", "use_mail", "use_active"]);
        return true;
    });

    await mountWithCleanup(AppCreator, {
        props: { onNewAppCreated: () => true },
    });
    await animationFrame();

    await contains(".o_web_studio_app_creator_next").click();

    await contains("input[name='appName']").click();
    await edit("testApp");
    await animationFrame();

    await contains(".o_web_studio_app_creator_next").click();

    await contains("input[name='menuName']").click();
    await edit("testMenu");
    await animationFrame();

    await contains(".o_web_studio_app_creator_next").click();

    expect(
        ".o_web_studio_model_configurator_option input[type='checkbox'][name='lines'][id='lines']"
    ).toHaveCount(1);
    expect("label[for='lines']").toHaveText(
        "Lines\nAdd details to your records with an embedded list view"
    );

    await contains(
        ".o_web_studio_model_configurator_option input[type='checkbox'][name='lines']"
    ).click();
    await contains(".o_web_studio_model_configurator_next").click();
});

test("app creator: debug flow with existing model", async () => {
    serverState.debug = "1";

    onRpc("ir.model", "name_search", ({ kwargs }) => {
        expect(kwargs.domain).toEqual([
            "&",
            "&",
            ["transient", "=", false],
            ["abstract", "=", false],
            "!",
            ["id", "in", []],
        ]);
        expect.step("name_search");
    });

    onRpc("/web_studio/create_new_app", async (request) => {
        const { params } = await request.json();
        expect.step("create-new-app");
        expect(params.model_id).toBe(1);
        return true;
    });

    await mountWithCleanup(AppCreator, {
        props: { onNewAppCreated: () => true },
    });
    await animationFrame();

    await contains(".o_web_studio_app_creator_next").click();

    await contains("input[name='appName']").click();
    await edit("testApp");
    await animationFrame();

    await contains(".o_web_studio_app_creator_next").click();

    await contains("input[name='menuName']").click();
    await edit("testMenu");
    await animationFrame();

    expect(".o_web_studio_app_creator_next.is_ready").toHaveCount(1);
    await contains("input[name='model_choice'][value='existing']").click();
    expect(".o_web_studio_app_creator_next.is_ready").toHaveCount(0);

    await contains(".o_record_selector input").click();
    await contains(".dropdown-item").click();

    await contains(".o_web_studio_app_creator_next").click();

    expect.verifySteps(["name_search", "create-new-app"]);
});

test("app creator: navigate through steps using 'ENTER'", async () => {
    expect.assertions(8);

    onRpc("/web_studio/create_new_app", async (request) => {
        const { params } = await request.json();
        expect(params.app_name).toBe("Kikou");
        expect(params.menu_name).toBe("Petite Perruche");
        expect(params.model_id).toBe(false);
        return true;
    });

    mockService("ui", {
        block: () => expect.step("UI blocked"),
        unblock: () => expect.step("UI unblocked"),
    });

    await mountWithCleanup(AppCreator, {
        props: { onNewAppCreated: () => expect.step("new-app-created") },
    });
    await animationFrame();

    expect(".o_web_studio_welcome").toHaveCount(1);

    await press("Enter");
    await animationFrame();

    expect(".o_web_studio_app_creator_name").toHaveCount(1);

    await press("Enter");
    await animationFrame();

    expect(".o_web_studio_app_creator_name").toHaveCount(1);
    await edit("Kikou");
    await animationFrame();

    await press("Enter");
    await animationFrame();

    expect(".o_web_studio_menu_creator").toHaveCount(1);

    await contains("input[name='menuName']").click();
    await edit("Petite Perruche");
    await animationFrame();

    await press("Enter");
    await animationFrame();
    await press("Enter");
    await animationFrame();
    expect.verifySteps(["UI blocked", "new-app-created", "UI unblocked"]);
});
