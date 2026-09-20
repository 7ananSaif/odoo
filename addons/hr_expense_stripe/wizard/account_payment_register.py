from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _name = 'account.payment.register'
    _inherit = ['account.payment.register']

    def _get_batch_available_journals(self, batch_result):
        # EXTEND account, filter out stripe issuing journals, as they are not used for making payments manually
        # This is to avoid confusion when selecting journals in the payment register
        journals = super()._get_batch_available_journals(batch_result)
        return journals.filtered(lambda jrnl: jrnl.bank_statements_source != 'stripe_issuing')
