import {
    click,
    insertText,
    openDiscuss,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";

import { describe, test } from "@odoo/hoot";

import {
    asyncStep,
    Command,
    serverState,
    onRpc,
    waitForSteps,
} from "@web/../tests/web_test_helpers";

import { defineWebsiteHelpdeskLivechatModels } from "@website_helpdesk_livechat/../tests/website_helpdesk_livechat_test_helpers";

describe.current.tags("desktop");
defineWebsiteHelpdeskLivechatModels();

test("can create a ticket from the thread action after the conversation ends", async () => {
    const pyEnv = await startServer();
    const groupId = pyEnv["res.groups"].create({ name: "Helpdesk Team" });
    serverState.groupHelpdeskId = groupId;
    pyEnv["res.users"].write([serverState.userId], {
        group_ids: [Command.link(groupId)],
    });
    const guestId = pyEnv["mail.guest"].create({ name: "Visitor" });
    const channel_id = pyEnv["discuss.channel"].create({
        channel_type: "livechat",
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ guest_id: guestId }),
        ],
        livechat_operator_id: serverState.partnerId,
    });
    onRpc("discuss.channel", "execute_command_helpdesk", ({ kwargs }) => {
        asyncStep(`execute command helpdesk. body: ${kwargs.body}`);
        return true;
    });
    await start();
    await openDiscuss(channel_id);
    await click(".o-mail-DiscussContent-header button[title='Create Ticket']");
    await insertText(".o-livechat-LivechatCommandDialog-form input", "test_ticket");
    await click(".o-mail-ActionPanel button", { text: "Create Ticket" });
    await waitForSteps(["execute command helpdesk. body: /ticket test_ticket"]);
});
