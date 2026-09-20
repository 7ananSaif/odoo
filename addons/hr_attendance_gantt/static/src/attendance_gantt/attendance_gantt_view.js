import { onRendered } from "@odoo/owl";
import { ganttView } from "@web_gantt/gantt_view";
import { registry } from "@web/core/registry";
import { AttendanceGanttModel } from "./attendance_gantt_model";
import { AttendanceGanttRenderer } from "./attendance_gantt_renderer";
import { GanttController } from "@web_gantt/gantt_controller";
import { AttendanceActionHelper } from "@hr_attendance/views/attendance_helper_view";

export class HrAttendanceGanttController extends GanttController {
    static template = "hr_attendance.AttendanceGanttController";
    static components = {
        ...GanttController.components,
        AttendanceActionHelper,
    }
    /**
     * @override
    */
    setup() {
        super.setup();
        this.loadHelper = true;
        // Will render noContentView only at the first loading
        onRendered(() => {
            this.loadHelper = false;
        });
    }

    get showNoContentHelp() {
        // Show if first row is empty (means no records)
        return this.model.data.rows.length < 2 && this.model.data.rows[0].recordIds.length === 0;
    }
}
const viewRegistry = registry.category("views");

export const attendanceGanttView = {
    ...ganttView,
    Controller: HrAttendanceGanttController,
    Model: AttendanceGanttModel,
    Renderer: AttendanceGanttRenderer,
};

viewRegistry.add("attendance_gantt", attendanceGanttView);
