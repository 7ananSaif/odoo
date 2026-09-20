import { useService } from "@web/core/utils/hooks";
import { serializeDate } from "@web/core/l10n/dates";


export function useOpenPayRun() {
    const action = useService("action");
    return (
        {
            id = null,
            date_start = null,
            date_end = null,
            structure_id = null,
            schedule_pay = null,
        }) => {
        if (id) {
            return action.doAction("hr_payroll.action_hr_payroll_open_pay_run", {
                additionalContext: {
                    search_default_payslip_run_id: id,
                }
            });
        }
        return action.doAction("hr_payroll.action_hr_payslip_run_create", {
            additionalContext: {
                ...(date_start ? { default_date_start: serializeDate(date_start) } : {}),
                ...(date_end ? { default_date_end: serializeDate(date_end) } : {}),
                ...(structure_id ? { default_structure_id: structure_id } : {}),
                ...(schedule_pay ? { default_schedule_pay: serializeDate(schedule_pay) } : {}),
            }
        });
    };
}
