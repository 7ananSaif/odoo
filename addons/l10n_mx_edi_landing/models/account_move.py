# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, _
from odoo.tools.misc import format_date


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _l10n_mx_edi_add_invoice_cfdi_values(self, cfdi_values):
        # OVERRIDE
        res = super()._l10n_mx_edi_add_invoice_cfdi_values(cfdi_values)
        if cfdi_values.get("errors"):
            return res

        customs_dates = self._l10n_mx_edi_get_formatted_date_per_customs_number()
        for base_line in cfdi_values['base_lines']:
            record = base_line['record']
            if not record.l10n_mx_edi_can_use_customs_invoicing:
                continue

            base_line_cfdi_values = base_line['l10n_mx_cfdi_values']
            customs_numbers = record._l10n_mx_edi_get_custom_numbers()
            formatted_dates = ",".join(
                customs_date for customs in customs_numbers
                if (customs_date := customs_dates.get(customs))
            )
            if formatted_dates:
                base_line_cfdi_values['description'] += _("\nCustoms Number Date: %s", formatted_dates)

        return res

    def _l10n_mx_edi_get_formatted_date_per_customs_number(self):
        self.ensure_one()
        landed_costs = self.env["stock.landed.cost"].sudo().search_fetch(
            [
                ("l10n_mx_edi_customs_number", "in",
                    self.invoice_line_ids.mapped("l10n_mx_edi_customs_number")),
                ("state", "=", "done"),
            ],
            field_names=["date"]
        )

        customs_dates = {}
        for lc in landed_costs:
            customs_dates[lc.l10n_mx_edi_customs_number] = (
                format_date(self.env, lc.date, date_format='yyyy-MM-dd')
                if lc.date else ''
            )
        return customs_dates
