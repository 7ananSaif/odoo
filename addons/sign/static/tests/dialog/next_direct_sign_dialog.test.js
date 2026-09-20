import { describe, expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { makeDialogMockEnv, mockService, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { user } from "@web/core/user";

import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { NextDirectSignDialog } from "@sign/dialogs/dialogs";
import { fakeSignInfoService } from "./dialog_utils";

const mountNextDirectSignDialog = async () => {
    const env = await makeDialogMockEnv();
    await mountWithCleanup(NextDirectSignDialog, { props: { close: () => {} } });
    return env;
};

const documentId = 23;
const signRequestState = "sent";
const tokenList = ["abc", "def"];
const nameList = ["Brandon", "Coleen"];

const signInfo = {
    documentId,
    createUid: 7,
    signRequestState,
    tokenList,
    nameList,
};

mockService("signInfo", fakeSignInfoService(signInfo));

describe.current.tags("desktop");
defineMailModels();

test("next direct sign dialog should render", async () => {
    await mountNextDirectSignDialog();
    expect(".o_nextdirectsign_message").toHaveCount(1, {
        message: "should render next direct sign message",
    });
    expect(".o_nextdirectsign_message p:first-child").toHaveText(
        "Your signature has been saved. Next signatory is Brandon",
        { message: "next signatory should be brandon" }
    );
    expect(".btn-primary").toHaveText("Next signatory (Brandon)");
});

test("next direct sign dialog should go to next document", async () => {
    await mountNextDirectSignDialog();
    mockService("action", {
        doAction(action, params) {
            expect(action.tag).toBe("sign.SignableDocument");
            const expected = {
                id: documentId,
                create_uid: user.userId,
                state: signRequestState,
                token: "abc",
                token_list: ["def"],
                name_list: ["Coleen"],
            };
            expect(params.additionalContext).toEqual(expected, {
                message: "action should be called with correct params",
            });
        },
    });

    await click(".btn-primary");
});
