import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { contains, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { IconCreator } from "@web_studio/client_action/icon_creator/icon_creator";

describe.current.tags("desktop");

const sampleIconUrl = "/web/Parent.src/img/default_icon_app.png";

defineMailModels();

test("icon creator: with initial web icon data", async () => {
    expect.assertions(4);

    await mountWithCleanup(IconCreator, {
        props: {
            editable: true,
            type: "base64",
            webIconData: sampleIconUrl,
            onIconChange(icon) {
                expect.step("icon-changed");
                expect(icon).toEqual({
                    backgroundColor: "#FFFFFF",
                    color: "#00CEB3",
                    iconClass: "fa fa-home",
                    type: "custom_icon",
                });
            },
        },
    });
    await animationFrame();

    expect(".o_web_studio_uploaded_image").toHaveStyle({
        backgroundImage: new RegExp(sampleIconUrl),
    });

    await contains(".o_web_studio_upload a").click();

    expect.verifySteps(["icon-changed"]);
    expect(".o_web_studio_upload input").toHaveAttribute("accept", "image/png");
});

test("icon creator: without initial web icon data", async () => {
    await mountWithCleanup(IconCreator, {
        props: {
            backgroundColor: "rgb(255, 0, 128)",
            color: "rgb(0, 255, 0)",
            editable: false,
            iconClass: "fa fa-heart",
            type: "custom_icon",
            onIconChange: () => {},
        },
    });

    expect(".o_app_icon").toHaveStyle({
        backgroundColor: "rgb(255, 0, 128)",
    });

    expect(".o_app_icon i").toHaveStyle({
        color: "rgb(0, 255, 0)",
    });

    expect(".o_app_icon i").toHaveClass(["fa", "fa-heart"]);
});
