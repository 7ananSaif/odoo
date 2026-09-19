# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    l10n_mx_cfdi_primary = fields.Boolean(compute='_compute_l10n_mx_cfdi_primary')
    l10n_mx_cfdi_secondary = fields.Boolean(compute='_compute_l10n_mx_cfdi_secondary')

    @api.depends('slip_ids.country_code', 'slip_ids.state', 'slip_ids.move_state')
    def _compute_l10n_mx_cfdi_primary(self):
        for run in self:
            run.l10n_mx_cfdi_primary = (
                all(p.state == 'paid' and p.move_state == 'posted' for p in run.slip_ids if p.country_code == 'MX') and
                not any(p.l10n_mx_edi_cfdi_uuid for p in run.slip_ids if p.country_code == 'MX')
            )

    @api.depends('slip_ids.country_code', 'slip_ids.l10n_mx_edi_cfdi_uuid')
    def _compute_l10n_mx_cfdi_secondary(self):
        for run in self:
            run.l10n_mx_cfdi_secondary = (
                any(p.l10n_mx_edi_cfdi_uuid for p in run.slip_ids if p.country_code == 'MX') and
                not all(p.l10n_mx_edi_cfdi_uuid for p in run.slip_ids if p.country_code == 'MX')
            )

    def action_generate_cfdi(self):
        for run in self:
            for payslip in run.slip_ids.filtered(lambda p: p.country_code == 'MX' and not p.l10n_mx_edi_cfdi_uuid):
                payslip.action_generate_cfdi()
            payslips_with_error = run.slip_ids.filtered(lambda p: p.country_code == 'MX' and not p.l10n_mx_edi_cfdi_uuid)
            if payslips_with_error:
                raise ValidationError(self.env._('The CFDI document could not be signed for some payslips:\n%s',
                                      '\n'.join(payslips_with_error.mapped('name'))))
