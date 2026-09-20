# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ar_arca_activity_id = fields.Many2one(
        'l10n_ar.arca.activity', string='Principal Activity',
        help="Principal registered activity of the company. This is used to generate the IVA Simple CSV Tax Reports.")
