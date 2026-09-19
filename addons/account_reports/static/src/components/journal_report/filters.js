import { _t } from "@web/core/l10n/translation";

import { AccountReport } from "@account_reports/components/account_report/account_report";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

export class JournalReportFilters extends AccountReportFilters {
    get filterExtraOptionsData() {
        return {
            ...super.filterExtraOptionsData,
            'show_payment_lines': {
                'name': _t("Include Payments"),
            },
        };
    }
};

AccountReport.registerCustomComponent(JournalReportFilters);
