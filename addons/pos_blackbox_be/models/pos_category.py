# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _
from odoo.exceptions import UserError
from odoo.fields import Domain


class PosCategory(models.Model):
    _inherit = "pos.category"

    def _load_pos_data_domain(self, data, config):
        domain = super()._load_pos_data_domain(data, config)
        if config.iface_fiscal_data_module and config.limit_categories:
            fdm_categ = self.env.ref("pos_blackbox_be.pos_category_fdm").id
            domain = Domain.OR([domain, Domain('id', '=', fdm_categ)])
        return domain

    @api.ondelete(at_uninstall=False)
    def _unlink_except_fiscal_category(self):
        restricted_category_id = self.env.ref("pos_blackbox_be.pos_category_fdm").id

        for pos_category in self.ids:
            if pos_category == restricted_category_id:
                raise UserError(_("Deleting this category is not allowed."))
