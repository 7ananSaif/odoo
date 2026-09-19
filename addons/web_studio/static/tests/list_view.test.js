import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { contains, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { defineStudioEnvironment } from "./studio_tests_context";

describe.current.tags("desktop");

defineStudioEnvironment();

test("add custom field button with other optional columns", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_app[data-menu-xmlid=app_3]").click();
    await animationFrame();

    expect(".o_list_view").toHaveCount(1);
    expect(".o_list_view .o_optional_columns_dropdown_toggle").toHaveCount(1);

    await contains(".o_optional_columns_dropdown_toggle").click();
    expect(".o-dropdown--menu .dropdown-item").toHaveCount(2);
    expect(".o-dropdown--menu .dropdown-item-studio").toHaveCount(1);

    await contains(".o-dropdown--menu .dropdown-item-studio").click();
    expect(".modal-studio").toHaveCount(0);
    expect(".o_studio .o_web_studio_editor .o_web_studio_list_view_editor").toHaveCount(1);
});

test("add custom field button without other optional columns", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_app[data-menu-xmlid=app_2]").click();
    await animationFrame();

    expect(".o_list_view").toHaveCount(1);
    expect(".o_list_view .o_optional_columns_dropdown_toggle").toHaveCount(1);

    await contains(".o_optional_columns_dropdown_toggle").click();
    expect(".o-dropdown--menu .dropdown-item").toHaveCount(1);
    expect(".o-dropdown--menu .dropdown-item-studio").toHaveCount(1);

    await contains(".o-dropdown--menu .dropdown-item-studio").click();
    expect(".modal-studio").toHaveCount(0);
    expect(".o_studio .o_web_studio_editor .o_web_studio_list_view_editor").toHaveCount(1);
});

test("should render the no content helper of studio actions", async () => {
    onRpc("/web_studio/get_studio_action", async () => {
        return {
            name: "Automated Actions",
            type: "ir.actions.act_window",
            res_model: "base.automation",
            views: [[false, "kanban"]],
            help: /*xml*/ `
                <p class="no_content_helper_class">
                    This text content is needed here, otherwise the paragraph won't be rendered.
                </p>
            `,
        };
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_app[data-menu-xmlid=app_2]").click();
    await animationFrame();
    await contains(".o_web_studio_navbar_item").click();
    await contains(".o_menu_sections button:contains(Automations)").click();
    expect(".no_content_helper_class").toHaveCount(1);
});
