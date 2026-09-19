# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    account_production_wip_account_id = fields.Many2one(
        comodel_name='account.account',
        string='WIP Account',
        readonly=False,
        related='company_id.account_production_wip_account_id',
    )

    account_production_wip_overhead_account_id = fields.Many2one(
        comodel_name='account.account',
        string='WIP Overhead Account',
        readonly=False,
        related='company_id.account_production_wip_overhead_account_id',
    )
