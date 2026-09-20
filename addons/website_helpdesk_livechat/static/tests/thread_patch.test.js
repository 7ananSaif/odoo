import {
    click,
    contains,
    insertText,
    openDiscuss,
    openFormView,
    registerArchs,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { describe, test } from "@odoo/hoot";
import { asyncStep, onRpc, serverState, waitForSteps } from "@web/../tests/web_test_helpers";
import { defineWebsiteHelpdeskLivechatModels } from "@website_helpdesk_livechat/../tests/website_helpdesk_livechat_test_helpers";

describe.current.tags("desktop");
defineWebsiteHelpdeskLivechatModels();

test("[technical] /ticket command gets a body as kwarg", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        channel_type: "channel",
        name: "General",
    });
    const messageId = pyEnv["mail.message"].create({
        model: "discuss.channel",
        res_id: channelId,
    });
    const [channelMemberId] = pyEnv["discuss.channel.member"].search([
        ["channel_id", "=", channelId],
        ["partner_id", "=", serverState.partnerId],
    ]);
    pyEnv["discuss.channel.member"].write([channelMemberId], {
        seen_message_id: messageId,
    });
    onRpc("discuss.channel", "execute_command_helpdesk", ({ kwargs }) => {
        asyncStep(`execute command helpdesk. body: ${kwargs.body}`);
        // random value returned in order for the mock server to know that this route is implemented.
        return true;
    });
    await start();
    await openDiscuss(channelId);
    await contains(".o-mail-DiscussContent-threadName[title='General']");
    await insertText(".o-mail-Composer-input", "/ticket something");
    await click(".o-mail-Composer button[title='Send']:enabled");
    await waitForSteps(["execute command helpdesk. body: /ticket something"]);
});

test("canned response should work in helpdesk ticket", async () => {
    const pyEnv = await startServer();
    pyEnv["mail.canned.response"].create({
        source: "hello",
        substitution: "Hello! How are you?",
    });
    const ticketId = pyEnv["helpdesk.ticket"].create({ name: "My helpdesk ticket" });
    registerArchs({
        "helpdesk.ticket,false,form": `
            <form>
                <sheet>
                    <field name="name"/>
                </sheet>
                <chatter/>
            </form>
        `,
    });
    await start();
    await openFormView("helpdesk.ticket", ticketId);
    await click(".o-mail-Chatter button", { text: "Send message" });
    await contains(".o-mail-Composer-suggestion strong", { count: 0, text: "hello" });

    await insertText(".o-mail-Composer-input", "::");
    await contains(".o-mail-Composer-suggestion strong", { text: "hello" });
});
