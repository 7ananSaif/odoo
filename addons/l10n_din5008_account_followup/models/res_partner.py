from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_din5008_date = fields.Date(default=fields.Date.today, store=False)
