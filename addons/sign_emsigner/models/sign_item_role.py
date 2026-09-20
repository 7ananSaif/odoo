# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SignItemRole(models.Model):
    _inherit = "sign.item.role"

    auth_method = fields.Selection(
        selection_add=[
            ('emsigner', 'Via Aadhar eSign'),
        ],
        ondelete={'emsigner': 'cascade'}
    )
