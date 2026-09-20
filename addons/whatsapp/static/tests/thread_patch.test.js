import { Composer } from "@mail/core/common/composer";
import { contains, openDiscuss, start, startServer } from "@mail/../tests/mail_test_helpers";
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

test("'Conversation Closed' banner must be visible only in deactivated whatsapp channels", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        name: "WhatsApp",
        channel_type: "whatsapp",
        whatsapp_channel_valid_until: serializeDateTime(DateTime.local().minus({ minutes: 1 })),
    });
    await start();
    await openDiscuss(channelId);
    await contains(".o-mail-Thread-banner", {
        text: "This conversation has been closed as more than 24 hours have passed since the last message received.",
    });

    // Active conversation should not have this button
    const [channel] = pyEnv["discuss.channel"].search_read([["id", "=", channelId]]);
    pyEnv["bus.bus"]._sendone(
        channel,
        "mail.record/insert",
        new mailDataHelpers.Store(pyEnv["discuss.channel"].browse(channelId), {
            whatsapp_channel_valid_until: DateTime.utc().plus({ days: 1 }).toSQL(),
        }).get_result()
    );
    await contains(".o-mail-Thread-banner", { count: 0 });
});
