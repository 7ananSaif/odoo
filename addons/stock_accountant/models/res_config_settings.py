# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

ACCOUNT_DOMAIN = [('account_type', 'not in', ('asset_receivable', 'liability_payable', 'asset_cash', 'liability_credit_card', 'off_balance'))]


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    valuation_method = fields.Selection(
        related="company_id.inventory_valuation", required=True,
        string="Inventory Valuation", readonly=False)
    cost_method = fields.Selection(
        related="company_id.cost_method", required=True,
        string="Inventory Cost Method", readonly=False)
    inventory_period = fields.Selection(
        related='company_id.inventory_period', required=True,
        string="Inventory Period", readonly=False)
    stock_journal = fields.Many2one(
        'account.journal', "Stock Journal", readonly=False,
        related='company_id.account_stock_journal_id')
    stock_valuation_account_id = fields.Many2one(
        'account.account', "Stock Valuation Account", readonly=False,
        related='company_id.account_stock_valuation_id')

    def action_stock_open_valued_locations(self):
        action = self.env["ir.actions.actions"]._for_xml_id('stock.action_prod_inv_location_form')
        action['context'] = {
            'search_default_inventory': 1,
            'search_default_prod_inv_location': 1,
        }
        return action
