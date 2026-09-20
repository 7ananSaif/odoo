import { _t } from "@web/core/l10n/translation";

import { AccountReport } from "@account_reports/components/account_report/account_report";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

export class L10nPHReportFilters extends AccountReportFilters {
    get filterExtraOptionsData() {
        return {
            ...super.filterExtraOptionsData,
            'include_no_tin': {
                'name': _t("Including Partners Without TIN"),
            },
        };
    }

    get selectedExtraOptions() {
        let selectedExtraOptionsName = super.selectedExtraOptions;

        if (this.controller.cachedFilterOptions.include_no_tin) {
            const includeNoTINName = _t("With Partners without TIN");

            selectedExtraOptionsName = selectedExtraOptionsName
                ? `${selectedExtraOptionsName}, ${includeNoTINName}`
                : includeNoTINName;
        }

        return selectedExtraOptionsName;
    }
};

AccountReport.registerCustomComponent(L10nPHReportFilters);
