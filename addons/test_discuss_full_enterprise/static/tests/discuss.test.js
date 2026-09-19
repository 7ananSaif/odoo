import { livechatLastAgentLeaveFromChatWindow } from "@im_livechat/../tests/im_livechat_shared_tests";

import {
    click,
    contains,
    focus,
    insertText,
    openDiscuss,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";

import { defineTestDiscussFullEnterpriseModels } from "@test_discuss_full_enterprise/../tests/test_discuss_full_enterprise_test_helpers";

import { insertText as htmlInsertText } from "@html_editor/../tests/_helpers/user_actions";

import { getService } from "@web/../tests/web_test_helpers";

import { describe, test } from "@odoo/hoot";

describe.current.tags("desktop");
defineTestDiscussFullEnterpriseModels();

test("[text composer] Can use channel command /who", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        channel_type: "channel",
        name: "my-channel",
    });
    await start();
    await openDiscuss(channelId);
    await insertText(".o-mail-Composer-input", "/who");
    await click(".o-mail-Composer button[title='Send']:enabled");
    await contains(".o_mail_notification", { text: "You are alone in this channel." });
});

test.tags("html composer");
test("Can use channel command /who", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        channel_type: "channel",
        name: "my-channel",
    });
    await start();
    const composerService = getService("mail.composer");
    composerService.setHtmlComposer();
    await openDiscuss(channelId);
    await focus(".o-mail-Composer-html.odoo-editor-editable");
    const editor = {
        document,
        editable: document.querySelector(".o-mail-Composer-html.odoo-editor-editable"),
    };
    await htmlInsertText(editor, "/who");
    await click(".o-mail-Composer button[title='Send']:enabled");
    await contains(".o_mail_notification", { text: "You are alone in this channel." });
});

test("live chat last agent leave from chat window", livechatLastAgentLeaveFromChatWindow);
