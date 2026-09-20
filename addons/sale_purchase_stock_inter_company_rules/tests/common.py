# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.sale_purchase_inter_company_rules.tests.common import TestInterCompanyRulesCommonSOPO


class TestInterCompanyRulesCommonStock(TestInterCompanyRulesCommonSOPO):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Required for `warehouse_id` and `discount` to be visible in the view
        cls.env.user.group_ids += (
            cls.env.ref('stock.group_stock_multi_warehouses')
            + cls.env.ref('account.group_delivery_invoice_address')
            + cls.env.ref('sale.group_discount_per_so_line')
        )

        # Set warehouse on company A
        cls.company_a.intercompany_warehouse_id = cls.env['stock.warehouse'].search([('company_id', '=', cls.company_a.id)])

        # Set warehouse on company B
        cls.company_b.intercompany_warehouse_id = cls.env['stock.warehouse'].search([('company_id', '=', cls.company_b.id)])

        cls.res_users_company_a.group_ids += (
            cls.env.ref('sales_team.group_sale_salesman')
            + cls.env.ref('purchase.group_purchase_user')
            + cls.env.ref('sale.group_discount_per_so_line')
        )
        cls.res_users_company_b.group_ids += (
            cls.env.ref('sales_team.group_sale_salesman')
            + cls.env.ref('purchase.group_purchase_user')
            + cls.env.ref('sale.group_discount_per_so_line')
        )
