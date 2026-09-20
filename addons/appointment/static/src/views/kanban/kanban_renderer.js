import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { AppointmentTypeActionHelper } from "@appointment/components/appointment_type_action_helper/appointment_type_action_helper";

export class AppointmentTypeKanbanRenderer extends KanbanRenderer {
    static template = "appointment.AppointmentTypeKanbanRenderer";
    static components = {
        ...KanbanRenderer.components,
        AppointmentTypeActionHelper,
    };
}
