import {
    SIZES,
    click,
    contains,
    openDiscuss,
    patchUiSize,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { describe, test } from "@odoo/hoot";
import { waitFor } from "@odoo/hoot-dom";
import { Command, serverState } from "@web/../tests/web_test_helpers";
import { defineWhatsAppModels } from "@whatsapp/../tests/whatsapp_test_helpers";

describe.current.tags("desktop");
defineWhatsAppModels();

test("Basic topbar rendering for whatsapp channels", async () => {
    const pyEnv = await startServer();
    const whatasspUser = pyEnv["res.partner"].create({ name: "Branden Freeman" });
    const channelId = pyEnv["discuss.channel"].create({
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: whatasspUser }),
        ],
        channel_type: "whatsapp",
        name: "WhatsApp 1",
        whatsapp_partner_id: whatasspUser,
    });
    await start();
    await openDiscuss(channelId);
    await contains(".o-mail-DiscussContent-header .o-mail-ThreadIcon .fa-whatsapp");
    await contains(".o-mail-DiscussContent-threadName", { value: "WhatsApp 1" });
    await waitFor(".o-mail-DiscussContent-header button:count(7)");
    await contains(".o-mail-DiscussContent-header button:eq(0)[title='Notification Settings']");
    await contains(".o-mail-DiscussContent-header button:eq(1)[title='Invite People']");
    await contains(".o-mail-DiscussContent-header button:eq(2)[title='Search Messages']");
    await contains(".o-mail-DiscussContent-header button:eq(3)[title='Attachments']");
    await contains(".o-mail-DiscussContent-header button:eq(4)[title='Pinned Messages']");
    await contains(".o-mail-DiscussContent-header button:eq(5)[title='Members']");
    await contains(".o-mail-DiscussContent-header button:eq(6)[title='View Contact']");
});

test("Invite users into whatsapp channel", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        name: "WhatsApp 1",
        channel_type: "whatsapp",
    });
    const partnerId = pyEnv["res.partner"].create({ name: "WhatsApp User" });
    pyEnv["res.users"].create({ partner_id: partnerId });
    await start();
    await openDiscuss(channelId);
    await click(".o-mail-DiscussContent-header button[title='Invite People']");
    await click(".o-discuss-ChannelInvitation-selectable");
    await click(".o-discuss-ChannelInvitation [title='Invite']:enabled");
    await contains(".o_mail_notification", { text: "invited WhatsApp User to the channel" });
});

test("Shows whatsapp user in member list", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({ name: "WhatsApp Partner" });
    const channelId = pyEnv["discuss.channel"].create({
        name: "WhatsApp 1",
        channel_type: "whatsapp",
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: partnerId }),
        ],
        whatsapp_partner_id: partnerId,
    });
    await start();
    await openDiscuss(channelId);
    await contains(".o-discuss-ChannelMember.cursor-pointer", { text: "Mitchell Admin" });
    await contains(".o-discuss-ChannelMemberList h6", { text: "WhatsApp User" });
    await contains(".o-discuss-ChannelMember:not(.cursor-pointer)", {
        text: "WhatsApp Partner",
        contains: [".o-mail-ImStatus [title='WhatsApp User']"],
    });
});

test("Mobile has WhatsApp category", async () => {
    const pyEnv = await startServer();
    patchUiSize({ size: SIZES.SM });
    pyEnv["discuss.channel"].create({ name: "WhatsApp 1", channel_type: "whatsapp" });
    await start();
    await openDiscuss();
    await click(".o-mail-MessagingMenu-navbar button", { text: "WhatsApp" });
    await contains(".o-mail-NotificationItem", { text: "WhatsApp 1" });
});

test("Can search whatsapp conversations on mobile", async () => {
    const pyEnv = await startServer();
    pyEnv["discuss.channel"].create({
        name: "slytherins",
        channel_type: "whatsapp",
    });
    patchUiSize({ size: SIZES.SM });
    await start();
    await openDiscuss();
    await click("button", { text: "WhatsApp" });
    await click(".o-mail-DiscussSearch-inputContainer");
    await click("a", { text: "slytherins" });
    await contains(".o-mail-ChatWindow-header div[title='slytherins']");
});

test("open whatsapp user's partner profile", async () => {
    const pyEnv = await startServer();
    const whatasspUser = pyEnv["res.partner"].create({ name: "Branden Freeman" });
    const channel = pyEnv["discuss.channel"].create({
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: whatasspUser }),
        ],
        channel_type: "whatsapp",
        whatsapp_partner_id: whatasspUser,
    });
    await start();
    await openDiscuss(channel);
    await click("button[title='View Contact']");
    await contains("div.o_field_widget > input:value(Branden Freeman)");
});
