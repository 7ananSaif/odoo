# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountSetupBankManualConfig(models.TransientModel):
    _inherit = 'account.setup.bank.manual.config'

    def validate(self):
        """ Default the bank statement source of new bank journals as 'file_import'
        """
        res = super().validate()
        if (self.num_journals_without_account_bank == 0 or self.linked_journal_id.bank_statements_source == 'undefined') \
          and self.env['account.journal']._get_bank_statements_available_import_formats():
            self.linked_journal_id.bank_statements_source = 'file_import'
        return res
