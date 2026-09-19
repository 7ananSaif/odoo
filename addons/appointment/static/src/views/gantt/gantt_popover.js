import { GanttPopover } from "@web_gantt/gantt_popover";


export class AppointmentGanttPopover extends GanttPopover {
    static template = "appointment.GanttPopover";
    static props = GanttPopover.props.concat(["headerClass"]);
    setup() {
        super.setup();
        this.displayPopoverHeader = true;
    }
}
