from odoo import _, models, api
from odoo.exceptions import UserError


class PosConfig(models.Model):
    _inherit = "pos.config"

    def _create_journal_and_payment_methods(self, cash_ref=None, cash_journal_vals=None):
        """ Override method to create the default credit card payment
        method for new point of sale configs"""
        journal, payment_method_ids = super()._create_journal_and_payment_methods(cash_ref=cash_ref, cash_journal_vals=cash_journal_vals)

        if self.env.company.chart_template == 'mx':
            l10n_mx_pm_credit_card = self.env.ref('l10n_mx_edi.payment_method_tarjeta_de_credito', raise_if_not_found=False)

            credit_card_pm = self.env['pos.payment.method'].search([
                ('journal_id.type', '=', 'bank'), ('company_id', 'parent_of', self.env.company.id),
                ('l10n_mx_edi_payment_method_id', '=', l10n_mx_pm_credit_card.id)], limit=1)
            if not credit_card_pm:
                bank_journal = self.env['account.journal'].search([('type', '=', 'bank'),
                    *self.env['account.journal']._check_company_domain(self.env.company)], limit=1)
                if not bank_journal:
                    raise UserError(_('Ensure that there is an existing bank journal. Check if chart of accounts is installed in your company.'))
                credit_card_pm = self.env['pos.payment.method'].create({
                    'name': _('Credit Card'),
                    'company_id': self.env.company.id,
                    'journal_id': bank_journal.id,
                    'sequence': 2,
                    'l10n_mx_edi_payment_method_id': l10n_mx_pm_credit_card.id
                })
            payment_method_ids.append(credit_card_pm.id)

        return journal, payment_method_ids

    @api.model
    def _load_pos_data_read(self, records, config):
        read_records = super()._load_pos_data_read(records, config)
        if read_records:
            l10n_mx_edi_fiscal_regime = self.env['ir.model.fields']._get('res.partner', 'l10n_mx_edi_fiscal_regime')
            l10n_mx_edi_usage = self.env['ir.model.fields']._get('account.move', 'l10n_mx_edi_usage')
            read_records[0]['_l10n_mx_edi_fiscal_regime'] = [{'value': s.value, 'name': s.name} for s in l10n_mx_edi_fiscal_regime.selection_ids]
            read_records[0]['_l10n_mx_edi_usage'] = [{'value': s.value, 'name': s.name} for s in l10n_mx_edi_usage.selection_ids]
            read_records[0]['_l10n_mx_country_id'] = self.env['res.country'].search([('code', '=', 'MX')], limit=1).id
        return read_records
