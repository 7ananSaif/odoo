import { _t } from "@web/core/l10n/translation";

import { AccountReport } from "@account_reports/components/account_report/account_report";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

export class L10nARTaxReportFilters extends AccountReportFilters {
    get selectedTaxType() {
        const availableTypes = Object.keys(this.controller.cachedFilterOptions.ar_vat_book_tax_types_available);
        const selectedTypes = Object.values(
            this.controller.cachedFilterOptions.ar_vat_book_tax_types_available,
        ).filter((type) => type.selected);

        if (selectedTypes.length === availableTypes.length || selectedTypes.length === 0) {
            return _t("All");
        }

        return selectedTypes.map((type) => type.name).join(", ");
    }

    selectArVatBookTaxType(taxType) {
        const newArVatBookTaxTypes = Object.assign(
            {},
            this.controller.cachedFilterOptions.ar_vat_book_tax_types_available,
        );
        newArVatBookTaxTypes[taxType]["selected"] = !newArVatBookTaxTypes[taxType]["selected"];
        this.filterClicked({ optionKey: "ar_vat_book_tax_types_available", optionValue: newArVatBookTaxTypes, reload: true});
    }
}

AccountReport.registerCustomComponent(L10nARTaxReportFilters);
