# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.account_inter_company_rules.tests.common import TestInterCompanyRulesCommon
from odoo import Command


class TestInterCompanyRulesCommonSOPO(TestInterCompanyRulesCommon):

    @classmethod
    def get_default_groups(cls):
        groups = super().get_default_groups()
        # give current user the rights to create sales orders
        return groups | cls.quick_ref('sales_team.group_sale_manager')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Required for `discount` to be visible on the form view
        cls.env.user.group_ids += cls.env.ref('sale.group_discount_per_so_line')
        # Required for `product_uom_id` to be visible on the form view
        cls.env.user.group_ids += cls.env.ref('uom.group_uom')

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

        # Create an auto applied fiscal position for each company
        (cls.company_a + cls.company_b).write({'country_id': cls.env.ref('base.us').id})
        cls.fp_a = cls.env['account.fiscal.position'].create({
            'name': f'Fiscal Position {cls.company_a.name}',
            'auto_apply': True,
            'country_id': cls.env.ref('base.us').id,
            'company_id': cls.company_a.id,
        })

        cls.fp_b = cls.env['account.fiscal.position'].create({
            'name': f'Fiscal Position {cls.company_b.name}',
            'auto_apply': True,
            'country_id': cls.env.ref('base.us').id,
            'company_id': cls.company_b.id,
        })

        # fiscal positions need some taxes to enable mapping - normally default taxes should belong to a domestic fiscal position
        (cls.company_a.account_sale_tax_id | cls.company_a.account_purchase_tax_id).fiscal_position_ids = [Command.link(cls.fp_a.id)]
        (cls.company_b.account_sale_tax_id | cls.company_b.account_purchase_tax_id).fiscal_position_ids = [Command.link(cls.fp_b.id)]
