# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PlanningRole(models.Model):
    _inherit = 'planning.role'

    product_ids = fields.One2many(
        'product.template',
        'planning_role_id',
        string='Services',
        domain="[('type', '=', 'service'), ('sale_ok', '=', True), '|', ('planning_role_id', '=', False), ('planning_role_id', '=', id)]",
    )

    @api.model
    def _ensure_uom_hours(self):
        uom_hours = self.env.ref('uom.product_uom_hour', raise_if_not_found=False)
        if not uom_hours:
            uom_hours = self.env['uom.uom'].create({
                'name': "Hours",
                'relative_factor': 1,
            })
            self.env['ir.model.data'].create({
                'name': 'product_uom_hour',
                'model': 'uom.uom',
                'module': 'uom',
                'res_id': uom_hours.id,
                'noupdate': True,
            })
