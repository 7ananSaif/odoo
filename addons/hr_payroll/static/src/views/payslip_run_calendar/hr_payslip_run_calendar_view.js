import { calendarView } from "@web/views/calendar/calendar_view";
import { PayRunCalendarController } from "./hr_payslip_run_calendar_controller";
import { registry } from "@web/core/registry";

const PayRunCalendarView = {
    ...calendarView,
    Controller: PayRunCalendarController,
    buttonTemplate: "hr_payroll.PayRunCalendarView.Buttons",
};

registry.category("views").add("pay_run_calendar", PayRunCalendarView);
