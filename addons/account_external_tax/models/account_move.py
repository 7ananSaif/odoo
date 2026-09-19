# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'account.external.tax.mixin']

    def button_draft(self):
        res = super().button_draft()
        self._filtered_external_tax_moves()._uncommit_external_taxes()
        return res

    def unlink(self):
        self._filtered_external_tax_moves()._void_external_taxes()
        return super().unlink()

    def _post(self, soft=True):
        """ Ensure taxes are correct before posting. """
        self._get_and_set_external_taxes_on_eligible_records()
        return super()._post(soft=soft)

    def _filtered_external_tax_moves(self):
        return self.filtered(lambda move: move.is_tax_computed_externally and
                                          not move._is_downpayment())

    def _get_and_set_external_taxes_on_eligible_records(self):
        """ account.external.tax.mixin override. """
        eligible_moves = self._filtered_external_tax_moves().filtered(lambda move: move.state != 'posted')
        eligible_moves._set_external_taxes(eligible_moves._get_external_taxes())
        return super()._get_and_set_external_taxes_on_eligible_records()

    def _get_line_data_for_external_taxes(self):
        """ account.external.tax.mixin override. """
        res = []
        base_lines_values = [value for value in self._get_rounded_base_and_tax_lines()[0] if not value['record']._get_downpayment_lines()]

        for base_line in base_lines_values:
            res.append({
                'base_line': base_line,
                'description': base_line['record'].name,
            })

        return res
