import { describe, expect, test } from "@odoo/hoot";
import { queryAllTexts, click } from "@odoo/hoot-dom";
import { mountView, onRpc, contains } from "@web/../tests/web_test_helpers";
import { defineSignModels, signModels } from "../mock_server/mock_models/sign_model";

describe.current.tags("desktop");
defineSignModels();

const formView = {
    type: "form",
    resModel: "sign.send.request",
    arch: `
        <form>
            <field name="signer_ids" widget="signer_x2many"/>
        </form>`,
};

test("basic rendering", async () => {
    onRpc("name_create", ({ args }) => {
        expect.step(`name_create ${args[0]}`);
    });

    await mountView({
        ...formView,
        resId: 1,
    });

    expect(".o_field_signer_x2many .d-flex.gap-2").toHaveCount(2, {
        message: "should contain two records",
    });
    expect(queryAllTexts(".o_field_signer_x2many .d-flex.gap-2 label")).toEqual([
        "Customer",
        "Company",
    ]);
    expect(".o_signer_one2many_mail_sent_order").toHaveCount(0, {
        message: "mail_sent_order should not be shown.",
    });

    await contains(".d-flex.gap-2 input").fill("john");
    await contains(".d-flex.gap-2 input").click();
    await click(".o_m2o_dropdown_option_create");

    expect.verifySteps(["name_create john"]);
});

test("rendering with set_sign_order", async () => {
    const { SignSendRequest } = signModels;
    SignSendRequest._records[0].set_sign_order = true;

    await mountView({
        ...formView,
        resId: 1,
    });

    expect(".o_field_signer_x2many .d-flex.gap-2").toHaveCount(2, {
        message: "should contain two records",
    });
    expect(queryAllTexts(".o_field_signer_x2many .d-flex.gap-2 label")).toEqual([
        "Customer",
        "Company",
    ]);
    expect(".o_signer_one2many_mail_sent_order").toHaveCount(2, {
        message: "mail_sent_order should not be shown.",
    });
});

test("rendering with only one role", async () => {
    await mountView({
        ...formView,
        resId: 2,
    });

    expect(".o_field_signer_x2many .d-flex.gap-2").toHaveCount(1, {
        message: "should contain two records",
    });
    expect(".o_field_signer_x2many .d-flex.gap-2 label").toHaveText("Company");
    expect(".o_signer_one2many_mail_sent_order").toHaveCount(0, {
        message: "mail_sent_order should not be shown.",
    });
});
