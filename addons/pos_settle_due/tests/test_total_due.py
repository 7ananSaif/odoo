import odoo

from odoo.addons.point_of_sale.tests.common import CommonPosTest


@odoo.tests.tagged('post_install', '-at_install')
class TestPointOfSaleFlow(CommonPosTest):
    def test_invoicing_after_closing_session(self):
        self.partner_moda.parent_id = self.partner_adgu
        self.pos_config_eur.payment_method_ids = [(4, self.credit_payment_method.id)]
        order, _ = self.create_backend_pos_order({
            'order_data': {
                'partner_id': self.partner_moda.id,
            },
            'line_data': [
                {'product_id': self.ten_dollars_no_tax.product_variant_id.id}
            ],
            'payment_data': [
                {'payment_method_id': self.bank_payment_method.id, 'amount': 5},
                {'payment_method_id': self.credit_payment_method.id, 'amount': 5},
            ],
            'pos_config': self.pos_config_eur
        })

        current_session = self.pos_config_eur.current_session_id
        current_session.action_pos_session_closing_control()

        accounting_partner = self.env['res.partner']._find_accounting_partner(self.partner_moda)
        accounting_partner._invalidate_cache()
        self.assertEqual(accounting_partner.total_due, 5.0)
        order.action_pos_order_invoice()
        self.assertEqual(accounting_partner.total_due, 5.0)

        # get journal entry that does the reverse payment, it the ref must contains Reversal
        reverse_payment = self.env['account.move'].search([('ref', 'ilike', "Reversal")])
        original_payment = self.env['account.move'].search([('ref', '=', current_session.display_name)])
        original_customer_payment_entry = original_payment.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        reverser_customer_payment_entry = reverse_payment.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        # check that both use the same account
        self.assertEqual(len(reverser_customer_payment_entry), 2)
        self.assertEqual(len(original_customer_payment_entry), 2)
        self.assertTrue(order.account_move.line_ids.partner_id == self.partner_moda.commercial_partner_id)
        self.assertEqual(reverser_customer_payment_entry[0].balance, -5.0)
        self.assertEqual(reverser_customer_payment_entry[1].balance, -5.0)
        self.assertEqual(reverser_customer_payment_entry[0].amount_currency, -5.0)
        self.assertEqual(reverser_customer_payment_entry[1].amount_currency, -5.0)
        self.assertEqual(original_customer_payment_entry.account_id.id, reverser_customer_payment_entry.account_id.id)
        self.assertEqual(reverser_customer_payment_entry.partner_id, original_customer_payment_entry.partner_id)

    def test_invoicing_after_closing_session_intermediary_account(self):
        """ Test that an invoice can be created after the session is closed """
        receivable_account = self.env.company.account_default_pos_receivable_account_id.copy()
        self.cash_payment_method.receivable_account_id = receivable_account
        self.partner_moda.parent_id = self.partner_adgu

        order, _ = self.create_backend_pos_order({
            'order_data': {
                'partner_id': self.partner_moda.id,
            },
            'line_data': [
                {'product_id': self.ten_dollars_no_tax.product_variant_id.id}
            ],
            'payment_data': [
                {'payment_method_id': self.cash_payment_method.id, 'amount': 10},
            ],
        })

        current_session = self.pos_config_usd.current_session_id
        current_session.action_pos_session_closing_control()
        accounting_partner = self.env['res.partner']._find_accounting_partner(self.partner_moda)
        self.assertEqual(accounting_partner.total_due, 0.0)

        # create invoice
        order.action_pos_order_invoice()
        self.assertEqual(accounting_partner.total_due, 0.0)

        # get journal entry that does the reverse payment, it the ref must contains Reversal
        reverse_payment = self.env['account.move'].search([('ref', 'ilike', "Reversal")])
        original_payment = self.env['account.move'].search([('ref', '=', current_session.display_name)])
        original_customer_payment_entry = original_payment.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        reverser_customer_payment_entry = reverse_payment.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        # check that both use the same account
        self.assertEqual(original_customer_payment_entry.account_id, receivable_account)
        self.assertEqual(original_customer_payment_entry.account_id.id, reverser_customer_payment_entry.account_id.id)
        self.assertEqual(reverser_customer_payment_entry.partner_id, original_customer_payment_entry.partner_id)
        aml_receivable = self.env['account.move.line'].formatted_read_group([('account_type', '=', 'asset_receivable')], groupby=['matching_number'], aggregates=['__count'])
        self.assertEqual(len(aml_receivable), 3)
        for aml_g in aml_receivable:
            self.assertEqual(aml_g['__count'], 2)

    def test_deleted_partner_get_all_total_due(self):
        """ Test that get_all_total_due works when some partners have been deleted """
        partner_a = self.env["res.partner"].create({"name": "A Partner"})
        partner_b = self.env["res.partner"].create({"name": "B Partner"})
        partner_c = self.env["res.partner"].create({"name": "C Partner"})

        partners = self.env['res.partner'].browse([partner_a.id, partner_b.id, partner_c.id])

        partner_b.unlink()
        self.assertEqual(len(partners.get_all_total_due(self.pos_config_usd.id)), 2)
