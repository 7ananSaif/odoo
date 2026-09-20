import { _t } from "@web/core/l10n/translation";

import { AccountReport } from "@account_reports/components/account_report/account_report";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

export class InstrastReportFilters extends AccountReportFilters {
    get selectedIntrastatOptions() {
        let selectedIntrastatOptions = [];
        // display selected options if any is selected and not all are selected
        const selected = this.controller.cachedFilterOptions['intrastat_type']
            .filter((optType) => optType.selected)
            .map((optType) => optType.name);
        if (selected.length && selected.length != this.controller.cachedFilterOptions['intrastat_type'].length) {
            selectedIntrastatOptions.push(selected.join(", "));
        }

        selectedIntrastatOptions.push(
            this.controller.cachedFilterOptions.intrastat_extended ? _t("Extended mode") : _t("Standard mode"),
        );
        selectedIntrastatOptions.push(
            this.controller.cachedFilterOptions.intrastat_with_vat
                ? _t("Partners with VAT numbers")
                : _t("All partners"),
        );
        return selectedIntrastatOptions.join(", ");
    }
};

AccountReport.registerCustomComponent(InstrastReportFilters);
