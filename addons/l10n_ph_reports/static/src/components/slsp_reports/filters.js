import { _t } from "@web/core/l10n/translation";

import { AccountReport } from "@account_reports/components/account_report/account_report";
import {L10nPHReportFilters} from "@l10n_ph_reports/components/ph_reports/filters";

export class L10nPHSlspReportFilters extends L10nPHReportFilters {
    get filterExtraOptionsData() {
        return {
            ...super.filterExtraOptionsData,
            'include_imports': {
                'name': _t("Including Importations"),
            },
        };
    }

    get selectedExtraOptions() {
        let selectedExtraOptionsName = super.selectedExtraOptions;

        if (this.controller.cachedFilterOptions.include_imports) {
            const includeImportsName = _t("With Importations");
            selectedExtraOptionsName = selectedExtraOptionsName
                ? `${selectedExtraOptionsName}, ${includeImportsName}`
                : includeImportsName;
        }

        return selectedExtraOptionsName;
    }
}

AccountReport.registerCustomComponent(L10nPHSlspReportFilters);
