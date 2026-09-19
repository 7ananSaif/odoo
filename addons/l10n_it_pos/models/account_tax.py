from odoo import api, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    @api.model
    def _prepare_base_line_for_taxes_computation(self, record, **kwargs):
        # EXTENDS 'account'
        base_line = super()._prepare_base_line_for_taxes_computation(record, **kwargs)
        base_line['l10n_it_epson_printer'] = kwargs.get('l10n_it_epson_printer', False)
        return base_line

    @api.model
    def _add_tax_details_in_base_line(self, base_line, company, rounding_method=None):
        # EXTENDS 'account'
        if (
            base_line['l10n_it_epson_printer']
            and not base_line['special_mode']
            and len(base_line['tax_ids']) == 1
            and base_line['tax_ids'][0].amount_type == 'percent'
            and not base_line['tax_ids'][0].price_include
        ):
            new_base_line = self._prepare_base_line_for_taxes_computation(
                base_line,
                quantity=1,
                discount=0,
                l10n_it_epson_printer=False,
            )
            super()._add_tax_details_in_base_line(new_base_line, company, rounding_method=rounding_method)
            self._round_base_lines_tax_details([new_base_line], company)
            target_total_amount_currency = base_line['currency_id'].round(
                new_base_line['tax_details']['total_included_currency']
                * base_line['quantity']
                * (1 - (base_line['discount'] / 100.0))
            )
            new_base_line = self._prepare_base_line_for_taxes_computation(base_line)
            super()._add_tax_details_in_base_line(new_base_line, company, rounding_method=rounding_method)
            self._round_base_lines_tax_details([new_base_line], company)
            reduced_base_lines = self._reduce_base_lines_to_target_amount(
                base_lines=[new_base_line],
                company=company,
                amount_type='fixed',
                amount=target_total_amount_currency,
            )
            if reduced_base_lines:
                self._fix_base_lines_tax_details_on_manual_tax_amounts(
                    base_lines=reduced_base_lines,
                    company=company,
                )
                for key in ('manual_total_excluded_currency', 'manual_total_excluded', 'manual_tax_amounts'):
                    base_line[key] = reduced_base_lines[0][key]
        super()._add_tax_details_in_base_line(base_line, company, rounding_method=rounding_method)
