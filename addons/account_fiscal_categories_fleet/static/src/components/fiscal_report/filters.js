import { _t } from "@web/core/l10n/translation";

import { AccountReport } from "@account_reports/components/account_report/account_report";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

export class FiscalFleetFilters extends AccountReportFilters {
    get filterExtraOptionsData() {
        return {
            ...super.filterExtraOptionsData,
            'vehicle_split': {
                'name': _t("Vehicle Split"),
            },
        };
    }
}

AccountReport.registerCustomComponent(FiscalFleetFilters);
