import { CalendarController } from "@web/views/calendar/calendar_controller";
import { useOpenPayRun } from "../payslip_run_hook";

export class PayRunCalendarController extends CalendarController {
    setup() {
        super.setup();
        this.openPayRun = useOpenPayRun();
    }

    createRecord(record) {
        this.openPayRun({
            date_start: record.start,
            date_end: record.end ?? record.start?.plus({ month: 1, day: -1 }),
        });
    }

    async editRecord(record, context) {
        this.openPayRun({
            id: record.id,
        });
    }
}
