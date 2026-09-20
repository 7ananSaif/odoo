import { registry } from '@web/core/registry';
import { ganttView } from '@web_gantt/gantt_view';
import { ScheduleGanttModel } from './schedule_gantt_model';
import { ScheduleGanttRenderer } from './schedule_gantt_renderer';


export const scheduleGanttView = {
    ...ganttView,
    Model: ScheduleGanttModel,
    Renderer: ScheduleGanttRenderer,
};

registry.category('views').add('schedule_gantt', scheduleGanttView);
