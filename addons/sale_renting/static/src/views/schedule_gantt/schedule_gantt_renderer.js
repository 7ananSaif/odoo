import { GanttRenderer } from '@web_gantt/gantt_renderer';



export class ScheduleGanttRenderer extends GanttRenderer {
    /**
     * Callback method invoked after a reschedule operation.
     * Displays notifications and executes associated actions if provided.
     *
     * @param {Object} result - The reschedule result.
     * @param {Array<Object>} [result.notifications=[]] - Array of notifications to display.
     * @param {Array<Object>} [result.actions=[]] - Actions to execute.
     */
    openPlanDialogCallback({ notifications = [], actions = [] }) {
        notifications.forEach(notif => {
            this.notificationService.add(notif.message, { type: notif.type });
        });
        actions.forEach(action => {
            this.actionService.doAction(action, { onClose: () => this.model.fetchData() });
        });
    }
}
