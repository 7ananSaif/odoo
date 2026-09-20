import { GanttRowProgressBar } from "@web_gantt/gantt_row_progress_bar";

export class WorkEntriesGanttRowProgressBar extends GanttRowProgressBar {
    static template = "hr_work_entry_enterprise.WorkEntriesGanttRowProgressBar";

    get show() {
        return true;
    }

    get status() {
        const { ratio } = this.props.progressBar;
        return ratio === 100 ? "black" : "warning";
    }
}
