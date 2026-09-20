import {
    click,
    defineMailModels,
    openDiscuss,
    start,
    startServer,
    openFormView,
} from "@mail/../tests/mail_test_helpers";
import { describe, test, expect } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { defineModels } from "@web/../tests/web_test_helpers";
import { DocumentsDocument } from "../helpers/data";
import { DocumentsModels } from "@documents/../tests/helpers/data";

const { DocumentsTag, IrEmbeddedActions, MailAlias, MailAliasDomain } = DocumentsModels;

defineMailModels();
defineModels({ DocumentsDocument, DocumentsTag, IrEmbeddedActions, MailAlias, MailAliasDomain });
describe.current.tags("desktop");

test("open spreadsheet attachment in spreadsheet when clicking on it from a discuss channel", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        channel_type: "channel",
        name: "channel1",
    });
    const attachmentId = pyEnv["ir.attachment"].create({
        name: "test_spreadsheet",
        mimetype: "application/o-spreadsheet",
    });
    pyEnv["documents.document"].create({
        name: "Test Spreadsheet",
        spreadsheet_data: "{}",
        is_favorited: false,
        folder_id: 1,
        handler: "spreadsheet",
        attachment_id: attachmentId,
    });
    pyEnv["mail.message"].create({
        attachment_ids: [attachmentId],
        body: "<p>Test</p>",
        model: "discuss.channel",
        res_id: channelId,
        message_type: "comment",
    });
    await start();
    await openDiscuss(channelId);
    await click(".o-mail-AttachmentCard");
    await animationFrame();
    expect(".o-spreadsheet-topbar").toHaveCount(1, {
        message: "It should have opened the spreadsheet",
    });
});

test("open spreadsheet attachment in spreadsheet when clicking on it from a form view", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({
        name: "Test Partner",
        email: "test_partner",
    });
    const attachmentId = pyEnv["ir.attachment"].create({
        name: "test_spreadsheet",
        mimetype: "application/o-spreadsheet",
    });
    pyEnv["documents.document"].create({
        name: "Test Spreadsheet",
        spreadsheet_data: "{}",
        is_favorited: false,
        folder_id: 1,
        handler: "spreadsheet",
        attachment_id: attachmentId,
    });
    pyEnv["mail.message"].create({
        attachment_ids: [attachmentId],
        body: "<p>Test</p>",
        model: "res.partner",
        res_id: partnerId,
        message_type: "comment",
    });
    await start();
    await openFormView("res.partner", partnerId);
    await click(".o-mail-Chatter-attachFiles");
    await click(".o-mail-AttachmentCard");
    await animationFrame();
    expect(".o-spreadsheet-topbar").toHaveCount(1, {
        message: "It should have opened the spreadsheet",
    });
});
