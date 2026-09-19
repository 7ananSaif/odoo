from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    pos_urbanpiper_username = fields.Char(
        string='UrbanPiper Username',
        help='The username of the UrbanPiper api account.'
    )
    pos_urbanpiper_apikey = fields.Char(
        string='UrbanPiper API Key',
        help='The API key for accessing the UrbanPiper services.'
    )
