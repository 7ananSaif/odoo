from odoo.addons.point_of_sale.tests.common import CommonPosTest


class CommonPosBrEdiTest(CommonPosTest):
    @classmethod
    def setUpClass(self):
        super().setUpClass()

        self.env.user.group_ids += self.env.ref('account.group_account_manager')
        self.br_edi_edit_pos_configs(self)

    def br_edi_edit_pos_configs(self):
        journal_id = self.env['account.journal'].create({
            "type": "general",
            "name": "Point of Sale - Test",
            "code": "POSS - Test",
            "sequence": 20,
        })
        self.pos_config_usd.write({
            'journal_id': journal_id.id,
            'l10n_br_is_nfce': True,
            'l10n_br_invoice_serial': '1',
        })
        self.pos_config_usd.payment_method_ids.write({
            'l10n_br_payment_method': '01',
        })
