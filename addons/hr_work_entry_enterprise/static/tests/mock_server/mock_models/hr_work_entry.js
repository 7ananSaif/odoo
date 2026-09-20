import { HrWorkEntry } from "@hr_work_entry/../tests/mock_server/mock_models/hr_work_entry";
import { patch } from "@web/core/utils/patch";

patch(HrWorkEntry._views, {
    gantt: `
        <gantt js_class="work_entries_gantt"
               string="Work Entries"
               date_start="date"
               date_stop="date"
               color="color"
               create="0"
               default_group_by='employee_id'
               decoration-warning="state == 'conflict'"
               pill_label="True"
               scales="week,month"
               default_range="month"
               total_row="1"
               progress_bar="employee_id"
               precision="{'week': 'day:full', 'month': 'day:full'}"
               multi_create_view="multi_create_form"
               plan="0">
               <field name="state"/>
        </gantt>
    `,
});
