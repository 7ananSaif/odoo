# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.http import request


class PosBlackboxLogIp(models.Model):
    _name = 'pos.blackbox.log.ip'
    _description = 'POS Blackbox Log IP'

    ip = fields.Char(string='IP Address', required=True)
    _ip_unique = models.UniqueIndex('(ip)')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if result := self.search([('ip', '=', vals['ip'])]):
                return result
        return super().create(vals_list)

    def _log_ip(self, config_id, ip):
        # due to an error in the test when pos_blackbox_be is installed,
        # ip is now None and we check the ip in this method instead.
        # in the test, the request is unbound, so the ip can not be retrieved
        # from the request.

        if not request:
            return

        ip = request.geoip.ip
        if bool(config_id.certified_blackbox_identifier):
            self.create({'ip': ip})
        elif self.search_count([('ip', '=', ip)]):
            raise UserError(_("Fiscal Data Module Error. You cannot open an uncertified Point of Sale with this device."))
