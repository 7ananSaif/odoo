import { describe, expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import {
    contains,
    makeDialogMockEnv,
    mockService,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { SignRefusalDialog, ThankYouDialog } from "@sign/dialogs/dialogs";
import { fakeSignInfoService } from "./dialog_utils";

const createEnvForDialog = async () => await makeDialogMockEnv();

const mountSignRefusalDialog = async () => {
    await mountWithCleanup(SignRefusalDialog, {
        props: {
            close: () => {},
        },
    });
};

const documentId = 23;
const signRequestItemToken = "abc";

const signInfo = {
    documentId,
    signRequestItemToken,
};

mockService("signInfo", fakeSignInfoService(signInfo));

describe.current.tags("desktop");
defineMailModels();

test("sign refusal dialog should render", async () => {
    await mountSignRefusalDialog(await createEnvForDialog());

    expect(".o_sign_refuse_confirm_message").toHaveCount(1, { message: "should show textarea" });
    expect("button.refuse-button").toHaveCount(1, { message: "should show button" });
    expect("button.refuse-button").toHaveAttribute("disabled", undefined, {
        message: "button should be disabled at first render",
    });
});

test("sign refusal dialog should call refuse route when confirmed", async () => {
    onRpc(`/sign/refuse/${documentId}/${signRequestItemToken}`, () => {
        expect.step("refuse-route-called");
        return true;
    });

    await createEnvForDialog();
    mockService("dialog", {
        add(component) {
            if (component === ThankYouDialog) {
                expect.step("thank-you-dialog");
            }
        },
    });

    await mountSignRefusalDialog();

    await contains(".o_sign_refuse_confirm_message").edit("reason for refusal");
    expect("button.refuse-button").not.toHaveAttribute("disabled", undefined, {
        message: "button should be enabled after textarea is filled",
    });
    await click("button.refuse-button");

    expect.verifySteps(["refuse-route-called"]);
});

test("sign refusal dialog should show error dialog when rpc fails", async () => {
    onRpc(`/sign/refuse/${documentId}/${signRequestItemToken}`, () => {
        expect.step("refuse-route-called");
        return false;
    });

    await createEnvForDialog();
    mockService("dialog", {
        add(component) {
            if (component === AlertDialog) {
                expect.step("alert-dialog");
            }
        },
    });

    await mountSignRefusalDialog();

    await contains(".o_sign_refuse_confirm_message").edit("reason for refusal");
    expect("button.refuse-button").not.toHaveAttribute("disabled", undefined, {
        message: "button should be enabled after textarea is filled",
    });
    await click("button.refuse-button");

    expect.verifySteps(["refuse-route-called", "alert-dialog"]);
});
