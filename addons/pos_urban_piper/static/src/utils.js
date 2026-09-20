import { formatDateTime } from "@web/core/l10n/dates";
const { DateTime } = luxon;
/**
 * This method converts time from milliseconds to the user's time zone.
 */
export function getTime(time) {
    return formatDateTime(DateTime.fromMillis(time));
}
