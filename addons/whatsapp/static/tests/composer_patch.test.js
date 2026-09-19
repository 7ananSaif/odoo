import { Composer } from "@mail/core/common/composer";
import {
    click,
    contains,
    dragenterFiles,
    dropFiles,
    inputFiles,
    insertText,
    openDiscuss,
    pasteFiles,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { mailDataHelpers } from "@mail/../tests/mock_server/mail_mock_server";

import { beforeEach, describe, test } from "@odoo/hoot";
import { serializeDateTime } from "@web/core/l10n/dates";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { defineWhatsAppModels } from "@whatsapp/../tests/whatsapp_test_helpers";

const { DateTime } = luxon;

describe.current.tags("desktop");
defineWhatsAppModels();

beforeEach(() => {
    // Simulate real user interactions
    patchWithCleanup(Composer.prototype, {
        isEventTrusted() {
            return true;
        },
    });
});

test("Allow only single attachment in every message", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        name: "WhatsApp 1",
        channel_type: "whatsapp",
    });
    await start();
    await openDiscuss(channelId);
    const [file1, file2] = [
        new File(["hello, world"], "text.txt", { type: "text/plain" }),
        new File(["hello, world"], "text2.txt", { type: "text/plain" }),
    ];
    await contains(".o-mail-Composer");
    await click(".o-mail-Composer button[title='More Actions']"); // open
    await contains(".dropdown-item:contains('Attach Files')");
    await click(".o-mail-Composer button[title='More Actions']"); // close
    await inputFiles(".o-mail-Composer .o_input_file", [file1]);
    await contains(".o-mail-AttachmentContainer");
    await contains(".o-mail-AttachmentContainer:not(.o-isUploading):contains(text.txt) .fa-check");
    await contains(".o-mail-Composer button[title='More Actions']", { count: 0 });
    await pasteFiles(".o-mail-Composer-input", [file2]);
    await contains(".o-mail-AttachmentContainer");
    await contains(".o-mail-AttachmentContainer:not(.o-isUploading):contains(text.txt) .fa-check");
    await dragenterFiles(".o-mail-Composer-input", [file2]);
    await dropFiles(".o-Dropzone", [file2]);
    await contains(".o-mail-AttachmentContainer");
    await contains(".o-mail-AttachmentContainer:not(.o-isUploading):contains(text.txt) .fa-check");
});

test("Can not add attachment after copy pasting an attachment", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        name: "WhatsApp 1",
        channel_type: "whatsapp",
    });
    await start();
    await openDiscuss(channelId);
    const [file1, file2] = [
        new File(["hello, world"], "text.txt", { type: "text/plain" }),
        new File(["hello, world"], "text2.txt", { type: "text/plain" }),
    ];
    await pasteFiles(".o-mail-Composer-input", [file1]);
    await click(".o-mail-Composer button[title='More Actions']");
    await contains(".dropdown-item:contains('Attach Files')", { count: 0 });
    await contains(".o-mail-AttachmentContainer");
    await contains(".o-mail-AttachmentContainer:not(.o-isUploading):contains(text.txt) .fa-check");
    await pasteFiles(".o-mail-Composer-input", [file2]);
    await contains(".o-mail-AttachmentContainer");
    await contains(".o-mail-AttachmentContainer:not(.o-isUploading):contains(text.txt) .fa-check");
    await dragenterFiles(".o-mail-Composer-input", [file2]);
    await dropFiles(".o-Dropzone", [file2]);
    await contains(".o-mail-AttachmentContainer");
    await contains(".o-mail-AttachmentContainer:not(.o-isUploading):contains(text.txt) .fa-check");
});

test("Can not add attachment after drag dropping an attachment", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        name: "WhatsApp 1",
        channel_type: "whatsapp",
    });
    await start();
    await openDiscuss(channelId);
    const [file1, file2] = [
        new File(["hello, world"], "text.txt", { type: "text/plain" }),
        new File(["hello, world"], "text2.txt", { type: "text/plain" }),
    ];
    await dragenterFiles(".o-mail-Composer-input", [file1]);
    await dropFiles(".o-Dropzone", [file1]);
    await click(".o-mail-Composer button[title='More Actions']");
    await contains(".dropdown-item:contains('Attach Files')", { count: 0 });
    await contains(".o-mail-AttachmentContainer");
    await contains(".o-mail-AttachmentContainer:not(.o-isUploading):contains(text.txt) .fa-check");
    await pasteFiles(".o-mail-Composer-input", [file2]);
    await contains(".o-mail-AttachmentContainer");
    await contains(".o-mail-AttachmentContainer:not(.o-isUploading):contains(text.txt) .fa-check");
});

test("Disabled composer should be enabled after message from whatsapp user", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        name: "WhatsApp 1",
        channel_type: "whatsapp",
        whatsapp_channel_valid_until: serializeDateTime(DateTime.local().minus({ minutes: 1 })),
    });
    await start();
    await openDiscuss(channelId);
    await contains(".o-mail-Composer-input[readonly]");
    await click(".o-mail-Composer button[title='More Actions']:disabled"); // open
    await contains(".dropdown-item:contains('Attach Files'):disabled");
    await contains(".dropdown-item:contains('Voice Message'):disabled");
    await click(".o-mail-Composer button[title='More Actions']"); // close
    // stimulate the notification sent after receiving a message from whatsapp user
    const [channel] = pyEnv["discuss.channel"].search_read([["id", "=", channelId]]);
    pyEnv["bus.bus"]._sendone(
        channel,
        "mail.record/insert",
        new mailDataHelpers.Store(pyEnv["discuss.channel"].browse(channelId), {
            whatsapp_channel_valid_until: DateTime.utc().plus({ days: 1 }).toSQL(),
        }).get_result()
    );
    await click(".o-mail-Composer button[title='More Actions']:enabled"); // open
    await contains(".dropdown-item:contains('Attach Files'):enabled");
    await contains(".dropdown-item:contains('Voice Message'):enabled");
    await insertText(".o-mail-Composer-input:not([readonly])", "Hello");
    await contains(".o-mail-Composer button[title='Send']:enabled");
});

test("'Revive WhatsApp Conversation' button must be visible only in deactivated whatsapp channels", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        name: "WhatsApp",
        channel_type: "whatsapp",
        whatsapp_channel_valid_until: serializeDateTime(DateTime.local().minus({ minutes: 1 })),
    });
    await start();
    await openDiscuss(channelId);
    await contains("button[title='Revive WhatsApp Conversation']");

    // Active conversation should not have this button
    const [channel] = pyEnv["discuss.channel"].search_read([["id", "=", channelId]]);
    pyEnv["bus.bus"]._sendone(
        channel,
        "mail.record/insert",
        new mailDataHelpers.Store(pyEnv["discuss.channel"].browse(channelId), {
            whatsapp_channel_valid_until: DateTime.utc().plus({ days: 1 }).toSQL(),
        }).get_result()
    );
    await contains("button[title='Revive WhatsApp Conversation']", { count: 0 });
});

test("Allow channel commands for whatsapp channels", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        name: "WhatsApp 1",
        channel_type: "whatsapp",
    });
    await start();
    await openDiscuss(channelId);
    await insertText(".o-mail-Composer-input", "/");
    await contains(".o-mail-NavigableList-item", { text: "leaveLeave this channel" });
});
