import { GanttModel } from '@web_gantt/gantt_model';


export class ScheduleGanttModel extends GanttModel {
    async _reschedule(ids, data, context) {
        return this.orm.call(this.metaData.resModel, 'web_gantt_write', [ids, data], { context });
    }
}
