import { patch } from "@web/core/utils/patch";
import { accountTaxHelpers } from "@account/helpers/account_tax";
import { roundPrecision } from "@web/core/utils/numbers";

patch(accountTaxHelpers, {
    // EXTENDS 'account'
    prepare_base_line_for_taxes_computation(record, kwargs = {}) {
        const base_line = super.prepare_base_line_for_taxes_computation(record, kwargs);
        base_line.l10n_it_epson_printer = kwargs.l10n_it_epson_printer || false;
        return base_line;
    },

    // EXTENDS 'account'
    add_tax_details_in_base_line(base_line, company, { rounding_method = null } = {}) {
        if (
            base_line.l10n_it_epson_printer &&
            !base_line.special_mode &&
            base_line.tax_ids.length === 1 &&
            base_line.tax_ids[0].amount_type === "percent" &&
            !base_line.tax_ids[0].price_include
        ) {
            let new_base_line = this.prepare_base_line_for_taxes_computation(base_line, {
                quantity: 1.0,
                discount: 0.0,
                l10n_it_epson_printer: false,
            });
            super.add_tax_details_in_base_line(new_base_line, company, {
                rounding_method: rounding_method,
            });
            this.round_base_lines_tax_details([new_base_line], company);
            const target_total_amount_currency = roundPrecision(
                new_base_line.tax_details.total_included_currency *
                    base_line.quantity *
                    (1 - base_line.discount / 100.0),
                base_line.currency_id.rounding
            );
            new_base_line = this.prepare_base_line_for_taxes_computation(base_line);
            super.add_tax_details_in_base_line(new_base_line, company, {
                rounding_method: rounding_method,
            });
            this.round_base_lines_tax_details([new_base_line], company);
            const reduced_base_lines = this.reduce_base_lines_to_target_amount(
                [new_base_line],
                company,
                "fixed",
                target_total_amount_currency
            );
            if (reduced_base_lines.length) {
                this.fix_base_lines_tax_details_on_manual_tax_amounts(reduced_base_lines, company);
                for (const key of [
                    "manual_total_excluded_currency",
                    "manual_total_excluded",
                    "manual_tax_amounts",
                ]) {
                    base_line[key] = reduced_base_lines[0][key];
                }
            }
        }
        super.add_tax_details_in_base_line(base_line, company, {
            rounding_method: rounding_method,
        });
    },
});
