import { GanttPopover } from "@web_gantt/gantt_popover";
import { formatFloatTime } from "@web/views/fields/formatters";

export class WorkEntriesGanttPopover extends GanttPopover {
    static template = "hr_work_entry_enterprise.WorkEntriesGanttPopover";

    durationToStr(duration) {
        const durationStr = formatFloatTime(duration, {
            noLeadingZeroHour: true,
        }).replace(/(:00|:)/g, "h");
        return ` ${durationStr}`;
    }

    get renderingContext() {
        const context = super.renderingContext;
        return {
            ...context,
            durationToStr: this.durationToStr,
        };
    }
}
