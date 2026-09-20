# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    l10n_mx_sat_code = fields.Selection(
        selection=[
            ('01', '01'),
            ('02', '02'),
            ('03', '03'),
            ('04', '04')])
