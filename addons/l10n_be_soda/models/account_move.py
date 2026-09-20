from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_import_file_type(self, file_data):
        """ Identify SODA files. """
        # EXTENDS 'account'
        if file_data['attachment'] and file_data['xml_tree'] is not None and file_data['xml_tree'].tag == 'SocialDocument':
            return 'l10n_be.soda'
        return super()._get_import_file_type(file_data)

    def _get_edi_decoder(self, file_data, new=False):
        # EXTENDS 'account'
        if file_data['import_file_type'] == 'l10n_be.soda':
            return {
                'priority': 20,
                'decoder': self._soda_edi_decoder,
            }
        return super()._get_edi_decoder(file_data, new=new)

    def _soda_edi_decoder(self, move, file_data, new=False):
        if move.journal_id.type != 'general':
            return move.env._("SODA files can only be imported in misc journals.")

        if move.invoice_line_ids:
            return move._reason_cannot_decode_has_invoice_lines()

        move.journal_id._l10n_be_parse_soda_file(file_data['attachment'], skip_wizard=True, move=move)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def write(self, vals):
        if not self.env.user.has_group('account.group_account_user') \
           or 'account_id' not in vals:
            return super().write(vals)
        for line in self.filtered(lambda l: l.company_id.account_fiscal_country_id.code == 'BE'):
            suspense_account = line.company_id.account_journal_suspense_account_id
            if line.account_id == suspense_account:
                if mapping := self.env['soda.account.mapping'].search([
                    ('company_id', '=', line.company_id.id),
                    ('name', '=', line.name),
                    '|',
                        ('account_id', '=', False),
                        ('account_id', '=', suspense_account.id),
                ]):
                    mapping.account_id = vals['account_id']
        return super().write(vals)
