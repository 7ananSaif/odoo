# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = "hr.version"

    l10n_id_bpjs_jkk = fields.Float(string="BPJS JKK", groups="hr.group_hr_user", tracking=True)
    l10n_id_kode_ptkp = fields.Selection(
        selection=[
            ('tk0', "TK/0"),
            ('tk1', "TK/1"),
            ('tk2', "TK/2"),
            ('tk3', "TK/3"),
            ('k0', "K/0"),
            ('k1', "K/1"),
            ('k2', "K/2"),
            ('k3', "K/3")],
        string="PTKP Code",
        default="tk0",
        required=True,
        groups="hr.group_hr_user",
        tracking=True,
        help="Employee's tax category that depends on their marital status and number of children")

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "ID":
            whitelisted_fields += [
                'l10n_id_bpjs_jkk',
            ]
        return whitelisted_fields
