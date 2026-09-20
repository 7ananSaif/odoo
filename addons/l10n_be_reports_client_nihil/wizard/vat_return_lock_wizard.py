from odoo import api, fields, models


class L10n_BeVatReturnLockWizard(models.TransientModel):
    _inherit = "l10n_be_reports.vat.return.lock.wizard"

    client_nihil = fields.Boolean(string="Client Nihil", compute="_compute_client_nihil", precompute=True, store=True, readonly=False)
    should_display_client_nihil = fields.Boolean(compute="_compute_should_display_client_nihil")

    @api.depends('return_id')
    def _compute_should_display_client_nihil(self):
        for wizard in self:
            wizard.should_display_client_nihil = fields.Date.end_of(wizard.return_id.date_to, "year") == wizard.return_id.date_to

    @api.depends('should_display_client_nihil', 'return_id')
    def _compute_client_nihil(self):
        for wizard in self:
            if wizard.should_display_client_nihil:
                # client_nihil should be set to false only if we are finding at least one partner with an amount exceeding 250€
                wizard.client_nihil = not bool(self.env['account.move.line'].sudo()._read_group(
                    domain=[
                        ('date', '>=', fields.Date.start_of(wizard.return_id.date_from, "year")),
                        ('date', '<=', wizard.return_id.date_to),
                        ('company_id', 'in', wizard.return_id.company_ids.ids),
                        ('parent_state', '=', 'posted'),
                        ('partner_id', '!=', False),
                        ('partner_id.vat', 'ilike', 'BE%'),
                        ('move_type', 'in', ('out_invoice', 'out_refund')),
                        ('display_type', '=', 'product'),
                    ],
                    groupby=['partner_id'],
                    aggregates=['id:recordset', 'balance:sum'],
                    having=[('balance:sum', '<', '-250.0')],
                    limit=1,
                ))
            else:
                wizard.client_nihil = False

    def _get_submission_options_to_inject(self):
        result = super()._get_submission_options_to_inject()
        result['client_nihil'] = self.client_nihil
        return result
