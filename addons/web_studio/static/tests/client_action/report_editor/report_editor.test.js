import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { hover, waitFor } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { Component, onWillRender, useState, xml } from "@odoo/owl";
import {
    contains,
    makeMockEnv,
    mockService,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { ReportEditorModel } from "@web_studio/client_action/report_editor/report_editor_model";
import { defineStudioEnvironment } from "../../studio_tests_context";

describe.current.tags("desktop");

test("setting is in edition doesn't produce intempestive renders", async () => {
    defineMailModels();

    mockService("ui", {
        block: () => expect.step("block"),
        unblock: () => expect.step("unblock"),
    });

    const env = await makeMockEnv();

    class Child extends Component {
        static template = xml`<div class="child" t-esc="props.rem.isInEdition"/>`;
        static props = ["*"];
        setup() {
            onWillRender(() => expect.step("Child rendered"));
        }
    }

    class Parent extends Component {
        static components = { Child };
        static template = xml`
            <Child rem="rem" />
            <button class="test-btn" t-on-click="() => rem.setInEdition(false)">btn</button>
        `;
        static props = ["*"];

        setup() {
            this.rem = useState(
                new ReportEditorModel({ services: env.services, resModel: "partner" })
            );
            onWillRender(() => expect.step("Parent rendered"));
            this.rem.setInEdition(true);
        }
    }

    await mountWithCleanup(Parent);
    await animationFrame();

    expect.verifySteps(["block", "Parent rendered", "Child rendered"]);
    expect(".child").toHaveText("true");

    await contains("button.test-btn").click();

    expect(".child").toHaveText("false");
    expect.verifySteps(["unblock", "Child rendered"]);
});

test("reports tab disabled when no record", async () => {
    defineStudioEnvironment();
    onRpc("ir.model", "studio_model_infos", ({ args }) => ({
        is_mail_thread: true,
        record_ids: [],
        name: "Custom Partner Model",
        model: args[0],
    }));
    await mountWithCleanup(WebClientEnterprise);
    await contains("a.o_app[data-menu-xmlid=app_1]").click();
    await contains(".o_web_studio_navbar_item").click();
    expect(".o_web_studio_menu .o_menu_sections button:contains(Reports)").toHaveCount(1);
    expect(".o_web_studio_menu .o_menu_sections button:contains(Reports):disabled").toHaveCount(1);
    await hover(".o_web_studio_menu .o_menu_sections button:contains(Reports)");
    await waitFor(".o-overlay-item", { timeout: 1000 });
    expect(".o-overlay-item").toHaveText(
        "You cannot edit a report while there is no Custom Partner Model (partner)"
    );
});
