import { describe, expect, test } from "@odoo/hoot";
import {
    makeDialogMockEnv,
    mockService,
    mountWithCleanup,
    onRpc,
    contains,
} from "@web/../tests/web_test_helpers";
import { ItsmeDialog } from "@sign_itsme/dialogs/itsme_dialog";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

const route = "/sign/sign/23/abc";
const params = {
    test: true,
};

const mountItsmeDialog = async (additionalProps = {}) => {
    await makeDialogMockEnv();
    await mountWithCleanup(ItsmeDialog, {
        props: {
            route,
            params,
            onSuccess: () => {},
            close: () => {},
            ...additionalProps,
        },
    });
};

describe.current.tags("desktop");
defineMailModels();

test("itsme dialog is rendered correctly", async () => {
    await mountItsmeDialog();

    expect(".itsme_confirm").toHaveCount(1, { message: "should show itsme button" });
    expect(".itsme_cancel").toHaveCount(1, { message: "should show go back button" });
});

test("itsme dialog click itsme button should send request", async () => {
    onRpc(route, async (request) => {
        const { params: receivedParams } = await request.json();
        expect.step("request-sent");
        expect(receivedParams).toEqual(params, {
            message: "action should be called with correct params",
        });
        return { success: true, authorization_url: false };
    });

    const onSuccess = () => {
        expect.step("success");
    };

    await mountItsmeDialog({ onSuccess });

    await contains("button.itsme_confirm").click();
    expect.verifySteps(["request-sent", "success"]);
});

test("itsme dialog click itsme button should show error if rpc fails", async () => {
    const errorMessage = "error_in_dialog";
    onRpc(route, () => ({ success: false, message: errorMessage }));

    await mountItsmeDialog();

    mockService("dialog", {
        add(component, props) {
            if (component === AlertDialog && props.body === errorMessage) {
                expect.step("error-dialog");
            }
        },
    });
    await contains("button.itsme_confirm").click();
    expect.verifySteps(["error-dialog"]);
});
