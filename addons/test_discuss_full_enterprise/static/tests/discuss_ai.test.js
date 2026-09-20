import {
    click,
    contains,
    insertText,
    openDiscuss,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";

import { defineHrModels } from "@hr/../tests/hr_test_helpers";

import { expectElementCount } from "@html_editor/../tests/_helpers/ui_expectations";

import { describe, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";

describe.current.tags("desktop");
defineHrModels(); // FIXME: somehow test non-deterministically needs "hr.employee", cf. https://runbot.odoo.com/runbot/build/92414152

test("can handle command and disable mentions in AI composer", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        channel_type: "ai_composer",
        name: "my-ai-composer",
    });
    pyEnv["discuss.channel"].create({ name: "my-channel" });
    await start();
    await openDiscuss(channelId);
    await insertText(".o-mail-Composer-input", "/help");
    await click(".o-mail-Composer button[title='Send']:enabled");
    await contains(".o-mail-Message");
    await insertText(".o-mail-Composer-input", "@");
    await animationFrame();
    await expectElementCount(".o-mail-NavigableList-item", 0);
    await insertText(".o-mail-Composer-input", "#", { replace: true });
    await expectElementCount(".o-mail-NavigableList-item", 0);
});
