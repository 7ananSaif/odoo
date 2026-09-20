# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        res = super().session_info()
        res["groups"]["documents.group_documents_manager"] = self.env.user.has_group("documents.group_documents_manager")
        res["groups"]["documents.group_documents_user"] = self.env.user.has_group("documents.group_documents_user")
        res["groups"]["base.group_multi_company"] = self.env.user.has_group('base.group_multi_company')
        return res
