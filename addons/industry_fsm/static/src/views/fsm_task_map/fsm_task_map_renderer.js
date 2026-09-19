import { MapRenderer } from "@web_map/map_view/map_renderer";

import { formatDateTime } from "@web/views/fields/formatters";
import { parseDateTime } from "@web/core/l10n/dates";
import { Time } from "@web/core/l10n/time";

export class FsmTaskMapRenderer extends MapRenderer {
    static subTemplates = {
        ...MapRenderer.subTemplates,
        PinListItems: "industry_fsm.FsmTaskMapRenderer.PinListItems",
    };

    getFormattedTime(record) {
        const { planned_date_begin } = record;
        if (!planned_date_begin) {
            return "";
        }
        const datetime = parseDateTime(record.planned_date_begin);
        const time = Time.from(datetime.toObject());
        if (time) {
            return time.toString(false);
        }
        return formatDateTime(datetime, { showDate: false, showSeconds: false });
    }
}
