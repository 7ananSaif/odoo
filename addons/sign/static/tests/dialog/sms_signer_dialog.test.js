import { describe, expect, test } from "@odoo/hoot";
import { click, runAllTimers } from "@odoo/hoot-dom";
import {
    makeDialogMockEnv,
    mockService,
    mountWithCleanup,
    patchWithCleanup,
    onRpc,
    contains,
} from "@web/../tests/web_test_helpers";

import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { SMSSignerDialog } from "@sign/dialogs/dialogs";
import { fakeSignInfoService } from "./dialog_utils";

const mountSMSSignerDialog = async (postValidation = () => {}) => {
    await makeDialogMockEnv();
    await mountWithCleanup(SMSSignerDialog, {
        props: {
            signerPhone: fakePhoneNumber,
            postValidation: postValidation,
            close: () => {},
        },
    });
};

const fakePhoneNumber = "123456789";
const documentId = 23;
const signRequestItemToken = "abc";
const fakeCode = "1234";

const signInfo = {
    documentId,
    signRequestItemToken,
};

mockService("signInfo", fakeSignInfoService(signInfo));

describe.current.tags("desktop");
defineMailModels();

test("SMS Signer Dialog should be rendered", async () => {
    onRpc(`/sign/send-sms/${documentId}/${signRequestItemToken}/${fakePhoneNumber}`, () => {
        expect.step("sms-sent");
        return Promise.resolve(true);
    });

    await mountSMSSignerDialog((code) => {
        expect.step("post-validation");
        expect(code).toBe(fakeCode, {
            message: "post validation should be called with same code",
        });
    });

    expect(".o_sign_validate_sms").toHaveCount(1, { message: "should render verify SMS button" });
    expect(".o_sign_resend_sms").toHaveCount(1);
    expect("input[name='phone']").toHaveCount(1);
    expect("input[name='phone']").toHaveValue(fakePhoneNumber);

    await contains("button.o_sign_resend_sms").click();
    expect("button:contains('SMS Sent')").toHaveCount(1, {
        message: "should show 'SMS sent' while sending SMS",
    });
    expect.verifySteps(["sms-sent"]);

    await contains("#o_sign_public_signer_sms_input").edit(fakeCode);
    await click(".o_sign_validate_sms");
    expect.verifySteps(["post-validation"]);
});

test("SMS Signer Dialog should handle errors", async () => {
    onRpc(`/sign/send-sms/${documentId}/${signRequestItemToken}/${fakePhoneNumber}`, () => {
        expect.step("sms-failed");
        return Promise.resolve(false);
    });

    patchWithCleanup(SMSSignerDialog.prototype, {
        handleSMSError: () => {
            expect.step("handle-sms-error");
        },
    });

    await mountSMSSignerDialog();

    await contains("button.o_sign_resend_sms").click();
    expect.verifySteps(["sms-failed", "handle-sms-error"]);
});

test("SMS Signer Dialog timeout should enable re-send button", async () => {
    onRpc(`/sign/send-sms/${documentId}/${signRequestItemToken}/${fakePhoneNumber}`, () =>
        Promise.resolve(true)
    );

    await mountSMSSignerDialog();

    await contains("button.o_sign_resend_sms").click();
    await runAllTimers();
    expect("button:contains('Re-send SMS')").toHaveCount(1, {
        message: "re-send sms button should be rendered",
    });
});
