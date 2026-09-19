import { serializeDate } from "@web/core/l10n/dates";
import { useService } from "@web/core/utils/hooks";

export function useWorkEntryPayslip({ getEmployeeIds, getRange }) {
    const action = useService("action");
    const orm = useService("orm");
    return async() => {
        const { start, end } = getRange();
        const ids = await orm.create("hr.payslip.run", [{
            date_start: serializeDate(start),
            date_end: serializeDate(end),
        }]);
        await orm.call("hr.payslip.run","generate_payslips", [ids], {
            employee_ids: getEmployeeIds(),
        });
        await action.doAction(await orm.call("hr.payslip.run", "action_open_payslips", [ids]));
    };
}
