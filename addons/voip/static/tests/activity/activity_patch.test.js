import { describe, expect, test } from "@odoo/hoot";
import {
    click,
    contains,
    openFormView,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("Phone number is displayed in activity info.", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({});
    pyEnv["mail.activity"].create({
        phone: "+1-202-555-0182",
        res_id: partnerId,
        res_model: "res.partner",
    });
    await start();
    await openFormView("res.partner", partnerId);
    await contains(".o-mail-Activity-voip-phoneNumber", { text: "+1-202-555-0182" });
});

test("Click on phone number from activity info triggers a call.", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({});
    pyEnv["mail.activity"].create({
        phone: "+1-202-555-0182",
        res_id: partnerId,
        res_model: "res.partner",
    });
    await start();
    await openFormView("res.partner", partnerId);
    await click(".o-mail-Activity-voip-phoneNumber > a");
    expect(pyEnv["voip.call"].search_count([["phone_number", "=", "+1-202-555-0182"]])).toBe(1);
});
