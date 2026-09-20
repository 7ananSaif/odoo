import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { edit } from "@odoo/hoot-dom";
import { animationFrame, Deferred } from "@odoo/hoot-mock";
import {
    contains,
    defineMenus,
    getService,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { NewModelItem } from "@web_studio/client_action/editor/new_model_item/new_model_item";

describe.current.tags("desktop");

test("Add New Model", async () => {
    defineMailModels();
    defineMenus([
        {
            id: 1,
            children: [],
            name: "App",
            appID: 1,
            xmlid: "app_1",
        },
    ]);
    const def = new Deferred();

    onRpc("/web_studio/create_new_menu", async (request) => {
        const { params } = await request.json();
        expect(params.menu_name).toBe("ABCD");
        expect(params.model_options).toEqual(["use_sequence", "use_mail", "use_active"]);
        await def;
        return { action_id: 99999 };
    });

    onRpc("/web/action/load", async (request) => {
        const { params } = await request.json();
        expect.step(`loadAction ${params.action_id}`);
        return true;
    });

    await mountWithCleanup(NewModelItem);
    await animationFrame();

    await getService("menu").setCurrentMenu(1);
    await animationFrame();

    expect(".o_web_studio_new_model_modal").toHaveCount(0);
    expect(".o_web_create_new_model").toHaveCount(1);

    await contains(".o_web_create_new_model").click();
    expect(".o_web_studio_new_model_modal").toHaveCount(1);
    expect("input[name='model_name']").toHaveCount(1);
    expect("input[name='model_name']").toBeFocused();
    await edit("ABCD");
    await contains("footer .btn-primary").click();
    expect("input[name='use_partner']").toHaveCount(1);

    await contains(".o_web_studio_model_configurator_next").click();
    expect(".o_web_studio_model_configurator").toHaveCount(0);
    expect(".o_web_studio_new_model_modal").toHaveCount(0);
    def.resolve();
    await expect.waitForSteps(["loadAction 99999"]);
});
