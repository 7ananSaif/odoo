import { describe, expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import {
    contains,
    makeDialogMockEnv,
    mockService,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";

import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { PublicSignerDialog } from "@sign/dialogs/dialogs";
import { fakeSignInfoService } from "./dialog_utils";

const mountPublicSignerDialog = async (additionalProps = {}) => {
    await makeDialogMockEnv();
    await mountWithCleanup(PublicSignerDialog, {
        props: {
            name: fakeName,
            mail: fakeMail,
            postValidation: () => {},
            close: () => {},
            ...additionalProps,
        },
    });
};

const fakeName = "Pericles";
const fakeMail = "pericles@test.com";
const documentId = 23;
const signRequestToken = "abc";

const signInfo = {
    documentId,
    signRequestToken,
};

mockService("signInfo", fakeSignInfoService(signInfo));

describe.current.tags("desktop");
defineMailModels();

test("public signer dialog is rendered correctly", async () => {
    await mountPublicSignerDialog();

    expect("#o_sign_public_signer_name_input").toHaveCount(1, {
        message: "should contain name input",
    });
    expect("#o_sign_public_signer_name_input").toHaveValue(fakeName, {
        message: "name should be prefilled",
    });
    expect("#o_sign_public_signer_mail_input").toHaveCount(1, {
        message: "should contain email input",
    });
    expect("#o_sign_public_signer_mail_input").toHaveValue(fakeMail, {
        message: "mail should be prefilled",
    });
    expect("button.btn-primary:contains('Validate & Send')").toHaveCount(1, {
        message: "should show validate button",
    });
});

test("public signer dialog correctly submits data", async () => {
    const mockAccessToken = "zyx";
    const mockRequestId = 11;
    const mockRequestToken = "def";
    onRpc(`/sign/send_public/${documentId}/${signRequestToken}`, async (request) => {
        const { params } = await request.json();
        if (params.name === fakeName && params.mail === fakeMail) {
            expect.step("sign-public-success");
            return {
                requestID: mockRequestId,
                requestToken: mockRequestToken,
                accessToken: mockAccessToken,
            };
        }
    });

    await mountPublicSignerDialog({
        postValidation: (requestId, requestToken, accessToken) => {
            expect(requestId).toBe(mockRequestId);
            expect(requestToken).toBe(mockRequestToken);
            expect(accessToken).toBe(mockAccessToken);
        },
    });
    await click(".btn-primary");
    expect.verifySteps(["sign-public-success"]);
});

test("public signer dialog inputs validation", async () => {
    await mountPublicSignerDialog({
        name: "",
    });

    expect("#o_sign_public_signer_name_input").not.toHaveClass("is-invalid");
    await click(".btn-primary");
    expect("#o_sign_public_signer_name_input").toHaveClass("is-invalid");

    expect("#o_sign_public_signer_mail_input").not.toHaveClass("is-invalid");
    await contains("#o_sign_public_signer_mail_input").edit("abc");
    await click(".btn-primary");
    expect("#o_sign_public_signer_mail_input").toHaveClass("is-invalid");

    await contains("#o_sign_public_signer_mail_input").edit(fakeMail);
    await click(".btn-primary");
    expect("#o_sign_public_signer_name_input").toHaveClass("is-invalid");
    expect("#o_sign_public_signer_mail_input").not.toHaveClass("is-invalid");
});
