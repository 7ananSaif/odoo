import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { animationFrame, click, queryAll } from "@odoo/hoot-dom";
import { user } from "@web/core/user";
import {
    makeDialogMockEnv,
    mountWithCleanup,
    onRpc,
    contains,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { SignNameAndSignatureDialog } from "@sign/dialogs/dialogs";

const mountSignNameAndSignatureDialog = async () => {
    onRpc("/web/sign/get_fonts/*", () => Promise.resolve({}));
    await makeDialogMockEnv();
    await mountWithCleanup(SignNameAndSignatureDialog, {
        props: {
            signature: {
                name,
            },
            frame: {},
            signatureType: "signature",
            displaySignatureRatio: 1,
            activeFrame: true,
            defaultFrame: "",
            mode: "auto",
            hash,
            onConfirm: () => {},
            onConfirmAll: () => {},
            close: () => {},
        },
    });
};

const name = "Brandon Freeman";
const hash = "abcdef...";

describe.current.tags("desktop");
defineMailModels();

test("sign name and signature dialog renders correctly", async () => {
    onRpc("has_group", () => true);
    await mountSignNameAndSignatureDialog();

    expect([...queryAll(".btn-primary, .btn-secondary")].map((el) => el.textContent)).toEqual(
        ["Sign all", "Sign", "Cancel"],
        { message: "should show buttons" }
    );
    expect(".mt16").toHaveCount(1, {
        message: "should show legal info about using odoo signature",
    });
    expect('input[name="signer"]').toHaveValue(name, { message: "Should auto-fill the name" });
    expect(".form-check").toHaveCount(1, { message: "should show frame in dialog" });
    expect(".form-check").not.toHaveClass("d-none", { message: "frame should be shown" });
    expect(".o_sign_frame.active").toHaveCount(1);
    expect(".o_sign_frame.active p").toHaveAttribute("hash", hash, {
        message: "hash should be in the signature dialog",
    });
});

test("sign name and signature dialog - frame is hidden when user is not from the sign user group", async () => {
    patchWithCleanup(user, { hasGroup: () => Promise.resolve(false) });
    await mountSignNameAndSignatureDialog();
    expect(".form-check").toHaveClass("d-none", { message: "frame should be hidden" });
});

test("sign name and signature dialog toggles active class on frame input change", async () => {
    onRpc("has_group", () => true);
    await mountSignNameAndSignatureDialog();

    expect(".o_sign_frame").toHaveClass("active");
    await click(".form-check-input");
    await animationFrame();
    expect(".o_sign_frame").not.toHaveClass("active", { message: "should hide frame" });
    await click(".form-check-input");
    await animationFrame();
    expect(".o_sign_frame").toHaveClass("active");
});

test("sign name and signature dialog default font", async () => {
    onRpc("/web/sign/get_fonts/*", (request) => {
        expect.step(new URL(request.url).pathname);
        return Promise.resolve([]);
    });
    onRpc("has_group", () => true);
    const mountSignNameAndSignatureDialogSaved = async () => {
        await makeDialogMockEnv();
        await mountWithCleanup(SignNameAndSignatureDialog, {
            props: {
                signature: {
                    name,
                },
                frame: {},
                signatureType: "signature",
                signatureImage:
                    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+BCQAHBQICJmhD1AAAAABJRU5ErkJggg==",
                displaySignatureRatio: 1,
                activeFrame: true,
                defaultFrame: "",
                mode: "draw",
                hash,
                onConfirm: () => {},
                onConfirmAll: () => {},
                close: () => {},
            },
        });
    };

    await mountSignNameAndSignatureDialogSaved();
    await click(".o_web_sign_auto_button");
    expect.verifySteps(["/web/sign/get_fonts/LaBelleAurore-Regular.ttf", "/web/sign/get_fonts/"]);
});

test("sign name and signature dialog draw mode does not allow to submit sign with no sign drawn", async () => {
    await mountSignNameAndSignatureDialog();

    expect(".o_web_sign_auto_button").toHaveClass("active");
    expect("footer.modal-footer > button.btn-primary").not.toHaveAttribute("disabled", undefined, {
        message: "Buttons should not be disabled on auto when Full name and Signature are filled",
    });

    await contains(".o_web_sign_draw_button").click();
    expect("footer.modal-footer > button.btn-primary").toHaveAttribute("disabled", undefined, {
        message: "Buttons should be disabled on draw if no signature is drawn",
    });
});

test("sign name and signature dialog - auto mode disables button on whitespace-only name", async () => {
    onRpc("has_group", () => true);

    await mountSignNameAndSignatureDialog();
    expect("footer.modal-footer > button.btn-primary").not.toHaveAttribute("disabled", "disabled", {
        message: "Sign all starts enabled",
    });

    await contains("input[name='signer']").edit("");
    expect("footer.modal-footer > button.btn-primary").toHaveAttribute("disabled", "", {
        message: "Sign all disabled on whitespace name",
    });
    expect("footer.modal-footer > button.btn-secondary:eq(0)").toHaveAttribute("disabled", "", {
        message: "Sign disabled on whitespace name",
    });
});
