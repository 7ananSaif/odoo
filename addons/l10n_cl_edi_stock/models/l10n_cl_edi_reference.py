# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class L10n_ClEdiReference(models.Model):
    _inherit = 'l10n_cl.edi.reference'

    picking_id = fields.Many2one('stock.picking', ondelete='cascade', string='Originating Delivery', index='btree_not_null')
