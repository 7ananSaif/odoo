# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _post_logout(cls):
        super()._post_logout()
        request.future_response.set_cookie('color_scheme', max_age=0)

    def color_scheme(self):
        cookie_scheme = request.httprequest.cookies.get('color_scheme')
        scheme = cookie_scheme if cookie_scheme else super().color_scheme()
        if user := request.env.user:
            if user._is_public():
                return super().color_scheme()
            if user_scheme := user.res_users_settings_id.color_scheme:
                if user_scheme in ('light', 'dark'):
                    return user_scheme
        return scheme

    def session_info(self):
        ICP = self.env['ir.config_parameter'].sudo()

        if self.env.user.has_group('base.group_system'):
            warn_enterprise = 'admin'
        elif self.env.user._is_internal():
            warn_enterprise = 'user'
        else:
            warn_enterprise = False

        result = super().session_info()
        result['support_url'] = "https://www.odoo.com/help"
        if warn_enterprise:
            result['warning'] = warn_enterprise
            result['expiration_date'] = ICP.get_param('database.expiration_date')
            result['expiration_reason'] = ICP.get_param('database.expiration_reason')
        return result
