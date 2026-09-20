# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.addons.mail.tools.discuss import Store


class ResUsers(models.Model):
    _inherit = "res.users"

    def _init_store_data(self, store: Store):
        super()._init_store_data(store)
        has_group = self.env.user.has_group("documents.group_documents_user")
        store.add_global_values(hasDocumentsUserGroup=has_group)
