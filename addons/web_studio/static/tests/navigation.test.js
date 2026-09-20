import { describe, expect, test } from "@odoo/hoot";
import { click, press, waitFor, delay } from "@odoo/hoot-dom";
import { animationFrame, Deferred } from "@odoo/hoot-mock";
import { Component, xml } from "@odoo/owl";
import {
    contains,
    defineActions,
    defineMenus,
    getService,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
    serverState,
    stepAllNetworkCalls,
} from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";
import { user } from "@web/core/user";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { StudioClientAction } from "@web_studio/client_action/studio_client_action";
import { FormEditorCompiler } from "@web_studio/client_action/view_editor/editors/form/form_editor_compiler";
import { FormEditorRenderer } from "@web_studio/client_action/view_editor/editors/form/form_editor_renderer/form_editor_renderer";
import { ListEditorRenderer } from "@web_studio/client_action/view_editor/editors/list/list_editor_renderer";
import { ViewEditor } from "@web_studio/client_action/view_editor/view_editor";
import { defineStudioEnvironment } from "./studio_tests_context";

describe.current.tags("desktop");

serverState.debug = "1";

defineStudioEnvironment();

test("Studio not available for non system users", async () => {
    patchWithCleanup(user, { isSystem: false });
    await mountWithCleanup(WebClientEnterprise);
    expect(".o_main_navbar").toHaveCount(1);
    expect(".o_main_navbar .o_web_studio_navbar_item button").toHaveCount(0);
});

test("Studio icon matches the clickbot selector", async () => {
    // This test looks stupid, but if you ever need to adapt the selector,
    // you must adapt it as well in the clickbot (in web), otherwise Studio
    // might not be tested anymore by the click_everywhere test.
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();
    expect(".o_web_studio_navbar_item:not(.o_disabled) i").toHaveCount(1);
});

test("open Studio with act_window and viewType", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();
    await click(".o_app[data-menu-xmlid=app_1]");
    await contains(".o_menu_sections .o_nav_entry:nth-child(2)").click();
    await animationFrame();

    expect(".o_list_view").toHaveCount(1);

    await click(".o_data_row .o_data_cell");
    await animationFrame();
    expect(".o_form_view").toHaveCount(1);

    await click(".o_web_studio_navbar_item button");
    await waitFor(".o_web_studio_editor_manager .o_web_studio_form_view_editor");

    expect('.o_field_widget[name="name"]').toHaveText("Yop");
});

test("reload the studio view", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_app[data-menu-xmlid=app_1]");
    await waitFor(".o_kanban_view");
    expect(".o_kanban_record:contains(Yop)").toHaveCount(1);

    await click(".o_kanban_record");
    await waitFor(".o_form_view");
    expect(".o_field_char input").toHaveValue("Yop");

    await click(".o_web_studio_navbar_item button");
    await waitFor(".o_web_studio_editor_manager");

    await getService("studio").reload();
    await animationFrame();

    await waitFor(".o_web_studio_editor_manager");
    expect(".o_form_view span:contains(Yop)").toHaveCount(1);
});

test("switch view and close Studio", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_app[data-menu-xmlid=app_1]");
    await waitFor(".o_kanban_record:contains(Yop)");

    await click(".o_web_studio_navbar_item button");
    await waitFor(".o_web_studio_editor_manager");

    await click(".o_web_studio_menu .o_menu_sections button");
    await waitFor(".o_web_studio_action_editor");

    await click(".o_web_studio_views .o_web_studio_thumbnail_item.o_web_studio_thumbnail_list");
    await waitFor(".o_web_studio_editor_manager");
    expect(".o_web_studio_list_view_editor").toHaveCount(1);

    await click(".o_web_studio_leave");
    await waitFor(".o_action_manager:first:not(:has(.o_studio))");
    await waitFor(".o_list_view");
    expect(".o_web_studio_editor_manager").toHaveCount(0);
});

test("navigation in Studio with act_window", async () => {
    stepAllNetworkCalls();

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    expect(".o_home_menu").toHaveCount(1);

    await click(".o_app[data-menu-xmlid=app_1]");
    await waitFor(".o_kanban_view");

    expect.verifySteps([
        "/web/webclient/translations",
        "/web/webclient/load_menus",
        "/mail/data",
        "/web/action/load",
        "get_views",
        "web_search_read",
        "has_group",
    ]);

    await contains(".o_web_studio_navbar_item button").click();
    await waitFor(".o_web_studio_editor_manager .o_web_studio_kanban_view_editor");

    expect.verifySteps([
        "studio_model_infos",
        "get_views",
        "/web_studio/get_studio_view_arch",
        "web_search_read",
    ]);

    expect(".o_kanban_record:contains(Yop)").toHaveCount(1);

    await click(".o_studio_navbar .o_menu_toggle");
    await waitFor(".o_studio_home_menu");
    await click(".o_app[data-menu-xmlid=app_2]");
    await waitFor(".o_list_view");

    expect.verifySteps([
        "/web/action/load",
        "/web/action/load_breadcrumbs",
        "studio_model_infos",
        "get_views",
        "/web_studio/get_studio_view_arch",
        "web_search_read",
    ]);

    await click(".o_web_studio_leave");
    await waitFor(".o_action_manager:first:not(:has(.o_studio))");
    await waitFor(".o_list_view");
    expect.verifySteps(["/web/action/load", "get_views", "web_search_read"]);

    expect(".o_web_studio_editor_manager").toHaveCount(0);
});

test("keep action context when leaving Studio", async () => {
    expect.assertions(2);
    let nbLoadAction = 0;
    onRpc("/web/action/load", async (request) => {
        nbLoadAction++;
        if (nbLoadAction === 3) {
            const res = await request.json();
            expect(res.params.context.active_id).toBe(1);
        }
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_app[data-menu-xmlid=app_1]");
    await waitFor(".o_kanban_view");

    await click(".o_nav_entry[data-menu-xmlid=menu_12]");
    await waitFor(".o_list_view");

    await contains(".o_web_studio_navbar_item button").click();
    await waitFor(".o_web_studio_editor_manager .o_web_studio_list_view_editor");

    await click(".o_web_studio_leave");
    await waitFor(".o_action_manager:first:not(:has(.o_studio))");
    await waitFor(".o_list_view");

    expect(nbLoadAction).toBe(3);
});

test("user context is unpolluted when entering studio in error", async () => {
    expect.errors(1);
    patchWithCleanup(StudioClientAction.prototype, {
        setup() {
            throw new Error("Boom");
        },
    });

    onRpc("partner", "get_views", ({ kwargs }) => {
        const context = kwargs.context;
        const options = kwargs.options;
        expect.step(
            `get_views, context studio: "${context.studio}", option studio: "${options.studio}"`
        );
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_app[data-menu-xmlid=app_1]");
    await waitFor(".o_kanban_view");
    expect.verifySteps([`get_views, context studio: "undefined", option studio: "undefined"`]);

    await contains(".o_web_studio_navbar_item button").click();
    expect(".o_web_studio_kanban_view_editor").toHaveCount(0);
    expect(".o_kanban_view").toHaveCount(1);
    expect.verifyErrors(["Boom"]);

    await click(".o_nav_entry[data-menu-xmlid=menu_12]");
    await waitFor(".o_list_view");
    expect.verifySteps([`get_views, context studio: "undefined", option studio: "undefined"`]);
});

test("user context is not polluted when getting views", async () => {
    onRpc("partner", "get_views", ({ kwargs }) => {
        const context = kwargs.context;
        const options = kwargs.options;
        expect.step(
            `get_views, context studio: "${context.studio}", option studio: "${options.studio}"`
        );
    });

    onRpc("/web_studio/get_studio_action", async () => {
        expect.step("get_studio_action");
        return {
            type: "ir.actions.act_window",
            res_model: "partner",
            views: [[false, "list"]],
            context: { studio: 1 },
        };
    });

    onRpc("web_search_read", ({ kwargs }) => {
        expect.step(`web_search_read, context studio: "${kwargs.context.studio}"`);
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_app[data-menu-xmlid=app_1]");
    await waitFor(".o_kanban_view");
    expect.verifySteps([
        `get_views, context studio: "undefined", option studio: "undefined"`,
        `web_search_read, context studio: "undefined"`,
    ]);

    await contains(".o_web_studio_navbar_item button").click();
    await waitFor(".o_web_studio_kanban_view_editor");
    expect.verifySteps([
        `get_views, context studio: "undefined", option studio: "true"`,
        `web_search_read, context studio: "1"`,
    ]);

    await contains(".o_menu_sections a[data-menu-xmlid=menu_12]").click();
    await waitFor(".o_list_view");
    expect.verifySteps([
        `get_views, context studio: "undefined", option studio: "true"`,
        `web_search_read, context studio: "1"`,
    ]);

    await contains(".o_web_studio_menu .o_menu_sections button:contains(Automations)").click();
    await waitFor(".o_web_studio_editor  :not(.o_web_studio_view_renderer) .o_list_view");
    expect.verifySteps([
        "get_studio_action",
        `get_views, context studio: "undefined", option studio: "undefined"`,
        `web_search_read, context studio: "1"`,
    ]);
});

test("error bubbles up if first rendering", async () => {
    expect.errors(1);
    patchWithCleanup(ListEditorRenderer.prototype, {
        setup() {
            throw new Error("Boom");
        },
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_app[data-menu-xmlid=app_1]");
    await waitFor(".o_kanban_view");
    await contains(".o_menu_sections a[data-menu-xmlid=menu_12]").click();
    await waitFor(".o_list_view");
    await contains(".o_web_studio_navbar_item button").click();
    await animationFrame();

    expect.verifyErrors(["Boom"]);
});

test("error when new app's view is invalid", async () => {
    expect.errors(1);

    defineActions([
        {
            xmlid: "testAction",
            id: 99,
            type: "ir.actions.act_window",
            res_model: "partner",
            views: [[false, "list"]],
            help: "",
            name: "test action",
            group_ids: [],
        },
    ]);

    defineMenus([
        {
            id: 99,
            children: [],
            actionID: 99,
            xmlid: "testMenu",
            name: "test",
            appID: 99,
        },
    ]);

    onRpc("/web_studio/create_new_app", async () => ({ menu_id: 99, action_id: 99 }));

    onRpc("/web_studio/get_studio_view_arch", async () => Promise.reject(new Error("Boom")));

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_web_studio_navbar_item button");
    await contains(".o_web_studio_new_app").click();
    await contains(".o_web_studio_app_creator_next").click();
    await contains(".o_web_studio_app_creator_name input").edit("testApp");
    await contains(".o_web_studio_app_creator_next").click();
    await contains(".o_web_studio_menu_creator input").edit("testMenu");
    await contains(".o_web_studio_model_configurator_next").click();
    await waitFor(".o_web_studio_action_editor");

    expect.verifyErrors(["Boom"]);
});

test("open same record when leaving form", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_app[data-menu-xmlid=app_2]");
    await waitFor(".o_list_view");

    await click(".o_data_row .o_data_cell:eq(1)");
    await waitFor(".o_form_view");

    expect(".o_form_view .o_field_widget[name=name] input").toHaveValue("Applejack");

    await contains(".o_web_studio_navbar_item button").click();
    await waitFor(".o_web_studio_editor_manager .o_web_studio_form_view_editor");

    expect(".o_form_view .o_field_widget[data-studio-xpath='/form[1]/field[1]'] span").toHaveText(
        "Applejack"
    );

    await click(".o_web_studio_leave");
    await waitFor(".o_action_manager:first:not(:has(.o_studio))");
    await waitFor(".o_form_view");

    expect(".o_form_view .o_field_widget[name=name] input").toHaveValue("Applejack");
});

test("open Studio with non editable view", async () => {
    onRpc("grid_unavailability", () => ({}));

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_app[data-menu-xmlid=app_1]");
    await waitFor(".o_kanban_view");

    await click(".o_switch_view.o_grid");
    await waitFor(".o_grid_view");

    await click(".o_web_studio_navbar_item button");
    await waitFor(".o_web_studio_action_editor");
});

test("open list view with sample data gives empty list view in studio", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_app[data-menu-xmlid=app_3]");
    await waitFor(".o_list_view");

    await contains(".o_web_studio_navbar_item button").click();
    await waitFor(".o_web_studio_editor_manager");

    expect(".o_list_table .o_data_row").toHaveCount(0);
});

test("kanban in studio should always ignore sample data", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_app[data-menu-xmlid=app_3]");
    await waitFor(".o_list_view");

    await click(".o_switch_view.o_kanban");
    await waitFor(".o_kanban_view");

    await contains(".o_web_studio_navbar_item button").click();
    await waitFor(".o_web_studio_editor_manager");

    expect(
        ".o_web_studio_kanban_view_editor .o_kanban_record:not(.o_kanban_ghost):not(.o_kanban_demo)"
    ).toHaveCount(1);
    expect(".o_web_studio_kanban_view_editor .o_view_nocontent").toHaveCount(0);
});

test("entering a kanban keeps the user's domain", async () => {
    onRpc("web_search_read", ({ kwargs, method }) => {
        expect.step(`${method}: ${JSON.stringify(kwargs.domain)}`);
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    expect.verifySteps([]);

    await click(".o_app[data-menu-xmlid=app_2]");
    await waitFor(".o_list_view");

    await click(".o_searchview_dropdown_toggler");

    expect.verifySteps([`web_search_read: []`]);

    await contains(".o_filter_menu .o_menu_item:contains(apple)").click();
    await animationFrame();

    expect.verifySteps([`web_search_read: [["name","ilike","Apple"]]`]);

    await click(".o_web_studio_navbar_item button");
    await waitFor(".o_web_studio_editor_manager");

    expect.verifySteps([`web_search_read: [["name","ilike","Apple"]]`]);

    expect(".o_list_table .o_data_row").toHaveCount(1);
});

test("open Studio with editable form view and check context propagation", async () => {
    expect.assertions(4);
    onRpc("pony", "onchange", ({ kwargs }) => {
        expect(kwargs.context.default_name).toBe("foo");
    });
    onRpc("partner", "onchange", ({ kwargs }) => {
        expect(kwargs.context).not.toInclude("default_name");
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_app[data-menu-xmlid=app_2]");
    await contains(".o_list_button_add").click();
    await waitFor(".o_form_view");

    await click(".o_web_studio_navbar_item button");
    await waitFor(".o_web_studio_editor_manager");

    await click(".o_web_studio_form_view_editor .o_field_one2many");
    await animationFrame();

    await click(
        `.o_web_studio_form_view_editor .o_field_one2many .o_web_studio_editX2Many[data-type="form"]`
    );
    await animationFrame();

    expect(".o_web_studio_editor_manager .o_web_studio_form_view_editor").toHaveCount(1);
});

test("concurrency: execute a non editable action and try to enter studio", async () => {
    const def = new Deferred();

    const webClient = await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    expect(".o_home_menu").toHaveCount(1);

    webClient.env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", () => {
        expect(".o_list_view").toHaveCount(1);
        expect(".o_web_studio_navbar_item.o_disabled").toHaveCount(1);
        def.resolve();
    });

    await click(".o_app[data-menu-xmlid=app_4]");
    await def;
    expect(".o_list_view").toHaveCount(1);
    expect(".o_web_studio_navbar_item.o_disabled").toHaveCount(1);
});

test("command palette inside studio", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_web_studio_navbar_item button");
    await waitFor(".o_studio_home_menu");

    await press("Space");
    await animationFrame();

    expect(".o_command_palette").toHaveCount(1);
    await click(".o_command_palette .o_command");
    await animationFrame();

    expect(".o_studio_home_menu").toHaveCount(0);
    expect(".o_studio .o_web_studio_kanban_view_editor").toHaveCount(1);
});

test("command palette inside studio with error", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_web_studio_navbar_item button");
    await waitFor(".o_studio_home_menu");

    await press(["S", "e", "t", "t"]);
    await animationFrame();
    await press("Enter");
    await animationFrame();
    expect("div.o_notification[role=alert]").toHaveCount(1);
});

test("leaving studio with a pending rendering in Studio", async () => {
    const def = new Deferred();
    let makeItWait = false;

    let dummyclass = "first-pass";
    class Dummy extends Component {
        static template = xml`<div class="dummy" t-att-class="classes" />`;
        static props = {};
        get classes() {
            return dummyclass;
        }
    }

    patchWithCleanup(FormEditorRenderer, {
        components: { ...FormEditorRenderer.components, Dummy },
    });

    patchWithCleanup(FormEditorCompiler.prototype, {
        compile() {
            const el = super.compile(...arguments);
            el.querySelector(".o_form_renderer").append(el.ownerDocument.createElement("Dummy"));
            return el;
        },
    });

    let vem;
    patchWithCleanup(ViewEditor.prototype, {
        setup() {
            super.setup();
            vem = this;
        },
    });

    onRpc("/web/action/load", async () => {
        if (makeItWait) {
            await def;
        }
    });

    onRpc("web_read", (params) => {
        if (makeItWait) {
            return [{ id: params.args[0], size: "big" }];
        }
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_app[data-menu-xmlid=app_2]");
    await waitFor(".o_list_view");

    await click(".o_data_cell");
    await animationFrame();

    await click(".o_web_studio_navbar_item button");
    await waitFor(".o_web_studio_editor_manager");

    expect(".dummy.first-pass").toHaveCount(1);

    stepAllNetworkCalls();
    makeItWait = true;
    await click(".o_web_studio_leave");
    dummyclass = "second-pass";
    vem.viewEditorModel.fields.size.selection.push(["big", "Big"]);
    await animationFrame();
    expect(".dummy.second-pass").toHaveCount(1);

    def.resolve();
    await def;
    await animationFrame();
    expect(".o_web_studio_editor_manager").toHaveCount(0);
    expect(".dummy").toHaveCount(0);

    expect.verifySteps(["/web/action/load", "web_read", "get_views", "web_read"]);
});

test("auto-save feature works in studio (not editing a view)", async () => {
    onRpc("/web_studio/get_studio_action", async () => ({
        name: "Automated Actions",
        type: "ir.actions.act_window",
        res_model: "base.automation",
        views: [
            [false, "list"],
            [false, "form"],
        ],
    }));

    onRpc("web_save", ({ args, model }) => {
        expect.step(`web_save: ${model}: ${JSON.stringify(args)}`);
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_app[data-menu-xmlid=app_1]");
    await waitFor(".o_kanban_view");

    await click(".o_web_studio_navbar_item button");
    await waitFor(".o_web_studio_editor_manager");

    await click(".o_menu_sections button:contains(Automations)");
    await contains(".o_web_studio_editor .o_list_button_add").click();
    await contains(".o_field_widget[name='name'] input").edit("created base automation");
    await animationFrame();

    await click(".o_web_studio_leave");
    await waitFor(".o_action_manager:first:not(:has(.o_studio))");
    await waitFor(".o_kanban_view");

    expect.verifySteps(['web_save: base.automation: [[],{"name":"created base automation"}]']);
});

test("load with active_id active_ids", async () => {
    expect.assertions(2);
    onRpc("onchange", ({ kwargs }) => {
        expect.step("onchange");
        expect(kwargs.context).toEqual({
            active_id: 1,
            active_ids: [1],
            allowed_company_ids: [1],
            lang: "en",
            studio: 1,
            tz: "taht",
            uid: 7,
        });
    });

    browser.location.href = "/odoo/action-1/studio";
    browser.location.search = "?mode=editor&_view_type=form&_tab=views&active_id=1";

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    expect.verifySteps(["onchange"]);
});

test("can edit ir.actions.act_window without id", async () => {
    onRpc("get_formview_action", ({ args }) => ({
        type: "ir.actions.act_window",
        res_model: "pony",
        target: "current",
        views: [[false, "form"]],
        res_id: args[0][0],
    }));
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await click(".o_app[data-menu-xmlid=app_1]");
    await contains(".o_kanban_view .o_kanban_record:not(.o_kanban_ghost)").click();
    await animationFrame();
    await click(".o_form_view .o_field_many2one_selection input");
    await click(".o_form_view .o_field_many2one_selection .o_external_button");
    await animationFrame();
    expect(".breadcrumb-item a:contains(Yop)").toHaveCount(1);
    await click(".o_web_studio_navbar_item button");
    await waitFor(".o_web_studio_editor_manager");

    expect(".o_field_widget[name='name']").toHaveText("Rainbow Dash");
    expect(browser.location.pathname).toBe("/odoo/action-1/1/m-pony/1/studio");
    expect(browser.location.search).toBe("?mode=editor&_tab=views&_view_type=form");

    await click(".o_menu_sections button:contains(Views)");
    await animationFrame();
    expect(
        ".o_web_studio_thumbnail_item:not(.disabled.pe-none):has(img[alt='View Form'])"
    ).toHaveCount(1);
    expect(".o_web_studio_thumbnail_item.pe-none").toHaveCount(10);

    await click(".o_web_studio_leave");
    await waitFor(".o_action_manager:first:not(:has(.o_studio))");
    await waitFor(".o_form_view");
    // The router pushes its state just after a setTimeout
    await delay(0);

    expect(".o_form_view .o_field_widget[name='name'] input").toHaveValue("Rainbow Dash");
    expect(".o_breadcrumb").toHaveText("partner Action\nYop\nRainbow Dash");
    expect(browser.location.pathname).toBe("/odoo/action-1/1/m-pony/1");
    expect(browser.location.search).toBe(""); // no view type in search means the default view type of the action is taken
});

test("enter and leave with multirecord view (invalid to load)", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        type: "ir.actions.act_window",
        views: [[false, "pivot"]],
        res_model: "partner",
        display_name: "some dynamic action",
    });

    await contains(".o_web_studio_navbar_item button").click();
    expect(".o_web_studio_view_renderer .o_pivot_view").toHaveCount(1);

    await contains(".o_web_studio_leave").click();
    await waitFor(".o_action_manager:first:not(:has(.o_studio))");
    await waitFor(".o_home_menu");
    expect(".o_main_navbar .o_menu_toggle").toHaveCount(0);
    expect(".o_studio").toHaveCount(0);
    expect(".o_menu_toggle_back").toHaveCount(0);
});

test("enter and leave on home menu with multirecord view (invalid to load)", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        type: "ir.actions.act_window",
        views: [[false, "pivot"]],
        res_model: "partner",
        display_name: "some dynamic action",
    });

    await contains(".o_web_studio_navbar_item button").click();
    expect(".o_web_studio_view_renderer .o_pivot_view").toHaveCount(1);

    await contains(".o_studio_navbar .o_menu_toggle").click();
    expect(".o_studio .o_home_menu").toHaveCount(1);

    await contains(".o_web_studio_leave").click();
    await waitFor(".o_action_manager:first:not(:has(.o_studio))");
    await waitFor(".o_home_menu");
    expect(".o_main_navbar .o_menu_toggle").toHaveCount(0);
    expect(".o_studio").toHaveCount(0);
    expect(".o_menu_toggle_back").toHaveCount(0);
});

test("enter and leave on home menu with multirecord view (invalid to load) and a valid one", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        type: "ir.actions.act_window",
        views: [[false, "form"]],
        res_model: "partner",
        display_name: "some dynamic action",
    });
    await waitFor(".o_form_view");

    await getService("action").doAction({
        type: "ir.actions.act_window",
        views: [[false, "pivot"]],
        res_model: "partner",
        display_name: "some dynamic action",
    });

    await contains(".o_web_studio_navbar_item button").click();
    expect(".o_web_studio_view_renderer .o_pivot_view").toHaveCount(1);

    await contains(".o_studio_navbar .o_menu_toggle").click();
    expect(".o_studio .o_home_menu").toHaveCount(1);

    await contains(".o_web_studio_leave").click();
    await waitFor(".o_action_manager:first:not(:has(.o_studio))");
    await waitFor(".o_home_menu");
    expect(".o_studio").toHaveCount(0);
    await contains(".o_menu_toggle_back").click();
    expect(".o_form_view").toHaveCount(1);
});
