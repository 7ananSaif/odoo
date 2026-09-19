import { ListRenderer } from '@web/views/list/list_renderer';

export class TimesheetsListRenderer extends ListRenderer {
    async onDeleteRecord(record) {
        if (record.data.is_timer_running) {
            // stop timer in parent record
            this.props.list.model.root.update({timer_start: false});
        }
        return await super.onDeleteRecord(record);
    }
}
