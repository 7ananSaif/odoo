# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests import freeze_time, tagged
from odoo.addons.sale_commission.tests.test_sale_commission_common import TestSaleCommissionCommon


@tagged('post_install', '-at_install')
class TestSaleSubCommissionUser(TestSaleCommissionCommon):

    @freeze_time("2024-04-02")
    def test_sub_commission_achievement_manager(self):
        self.commission_plan_manager.write({
            'periodicity': 'month',
            'type': 'achieve',
            'user_type': 'team',
        })
        self.commission_plan_manager.date_from = '2024-01-01'
        self.commission_plan_manager.date_to = '2024-12-31'
        (self.commission_user_1 + self.commission_user_2 + self.commission_manager).sale_team_id = self.team_commission
        self.commission_plan_manager.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
            'type': 'amount_invoiced',
            'rate': 1,
            'plan_id': self.commission_plan_user.id,
        }])
        self.commission_plan_manager.user_ids = [Command.create({
            'user_id': self.commission_user_1.id,
            'date_from': "2024-01-01"
        })]
        self.env['sale.commission.achievement'].create([{
            'date': '2024-03-03',
            'achieved': 100,
            'add_user_id': self.commission_plan_manager.user_ids[0].id,
            'reduce_user_id': self.commission_plan_manager.user_ids[1].id,
        }])
        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'user_id': self.commission_user_1.id,
            'order_line': [Command.create({
                'product_id': self.commission_product_1.id,
                'product_uom_qty': 10,
                'price_unit': 200,
            })],
            'team_id': self.commission_user_1.sale_team_id.id,
        })
        so.action_confirm()
        am = so._create_invoices()
        am._post()
        self.commission_plan_manager.action_approve()
        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_manager.id)])
        commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_manager.id)])
        manager_achievement = achievements.filtered(lambda a: a.user_id == self.commission_manager)
        user_achievement = achievements.filtered(lambda a: a.user_id == self.commission_user_1)
        self.assertAlmostEqual(sum(user_achievement.mapped('achieved')), 1900.0, msg="The user gets the amount (2000 - 100)")
        self.assertAlmostEqual(sum(manager_achievement.mapped('achieved')), 2100, msg="The manager send the amount (2000 + 100)")
        user_commissions = commissions.filtered(lambda c: c.user_id == self.commission_user_1)
        manager_commissions = commissions.filtered(lambda c: c.user_id == self.commission_manager)
        self.assertAlmostEqual(sum(user_commissions.mapped('achieved')), 1900, msg="The user gets the amount (2000 - 100)")
        self.assertAlmostEqual(sum(manager_commissions.mapped('achieved')), 2100, msg="The user gets the amount (2000 - 100)")

    @freeze_time("2024-04-01")
    def test_achievement_report_partner_id(self):
        """Ensure achievement lines carry the correct partner_id from sale order and invoice."""
        self.commission_plan_user.write({
            'periodicity': 'month',
            'type': 'achieve',
            'user_type': 'person',
        })
        self.commission_plan_user.action_approve()

        self.commission_plan_user.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
            'type': 'amount_invoiced',
            'rate': 0.1,
            'plan_id': self.commission_plan_user.id,
        }])

        self.commission_user_1.sale_team_id = self.team_commission

        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'user_id': self.commission_user_1.id,
            'order_line': [Command.create({
                'product_id': self.commission_product_1.id,
                'product_uom_qty': 5,
                'price_unit': 100,
            })],
            'team_id': self.commission_user_1.sale_team_id.id,
        })
        so.action_confirm()

        invoice = so._create_invoices()
        invoice._post()
        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        achievements = self.env['sale.commission.achievement.report'].search([
            ('plan_id', '=', self.commission_plan_user.id),
            ('related_res_model', '=', 'account.move'),
            ('related_res_id', '=', invoice.id),
        ])
        self.assertTrue(achievements, "There should be at least one achievement line from invoice.")
        self.assertEqual(
            achievements.partner_id, invoice.partner_id,
            f"Expected partner {invoice.partner_id.name} but got {achievements.partner_id.name} on achievement line"
        )
