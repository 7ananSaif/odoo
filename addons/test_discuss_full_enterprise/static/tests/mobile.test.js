import {
    mailCanAddMessageReactionMobile,
    mailCanCopyTextToClipboardMobile,
} from "@mail/../tests/mail_shared_tests";
import { describe, test } from "@odoo/hoot";
import { defineTestDiscussFullEnterpriseModels } from "@test_discuss_full_enterprise/../tests/test_discuss_full_enterprise_test_helpers";

describe.current.tags("mobile");
defineTestDiscussFullEnterpriseModels();

test("can add message reaction (mobile)", mailCanAddMessageReactionMobile);

test("can copy text to clipboard (mobile)", mailCanCopyTextToClipboardMobile);
