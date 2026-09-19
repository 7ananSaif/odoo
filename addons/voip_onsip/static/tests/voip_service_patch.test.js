import { start, startServer } from "@mail/../tests/mail_test_helpers";
import { describe, test, expect } from "@odoo/hoot";
import { defineVoipOnsipModels } from "@voip_onsip/../tests/voip_onsip_test_helpers";
import { serverState } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
defineVoipOnsipModels();

test("authorizationUsername is overridden to use onsip_auth_username.", async () => {
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({
        voip_username: "VoIP username",
        onsip_auth_username: "OnSIP username",
        user_id: serverState.userId,
    });
    const env = await start();
    expect(env.services.voip.authorizationUsername).toBe("OnSIP username");
});
