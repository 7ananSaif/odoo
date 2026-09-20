# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_co_dian_mandate_principal = fields.Many2one(comodel_name='res.partner', string="Mandate Principal")
