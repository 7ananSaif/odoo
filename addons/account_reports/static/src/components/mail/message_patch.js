import { Message } from "@mail/core/common/message";
import { patch } from "@web/core/utils/patch";
import { formatDate } from "@web/core/l10n/dates";

const { DateTime } = luxon;

patch(Message.prototype, {
    formatAccountReportsAnnotationDate(date) {
        return formatDate(DateTime.fromISO(date));
    },
});
