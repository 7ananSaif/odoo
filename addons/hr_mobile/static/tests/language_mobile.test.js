import { user } from "@web/core/user";
import { accountMethodsForMobile } from "@web_mobile/js/core/mixins";
import { methods as mobileNativeMethods } from "@web_mobile/js/services/core";
import { clickSave, defineModels, fields, models, mountView, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { expect, test } from "@odoo/hoot";

class Users extends models.Model {
    name = fields.Char();
}

defineModels([Users]);
defineMailModels();

const MY_IMAGE = 'iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==';
const BASE64_PNG_HEADER = "iVBORw0KGg";

test("EmployeeProfileFormView should call native updateAccount method when saving record", async () => {
    patchWithCleanup(mobileNativeMethods, {
        async updateAccount(options) {
            const { avatar, name, username } = options;
            expect.step("should call updateAccount");
            expect(avatar.startsWith(BASE64_PNG_HEADER)).toBe(true, {
                message: "should have a PNG base64 encoded avatar",
            });
            expect(name).toBe("Marc Demo");
            expect(username).toBe("demo");
        },
    });
    patchWithCleanup(user, { login: "demo", name: "Marc Demo" });
    patchWithCleanup(accountMethodsForMobile, {
        url(path) {
            if (path === "/web/image") {
                return `data:image/png;base64,${MY_IMAGE}`;
            }
            return super.url(...arguments);
        },
    });

    await mountView({
        type: "form",
        resModel: "users",
        arch: `
            <form js_class="hr_user_preferences_form">
                <sheet>
                    <field name="name"/>
                </sheet>
            </form>`,
    });

    await clickSave();
    expect.verifySteps(["should call updateAccount"]);
});
