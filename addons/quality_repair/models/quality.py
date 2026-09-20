# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class QualityPoint(models.Model):
    _inherit = "quality.point"

    @api.constrains('measure_on', 'picking_type_ids')
    def _check_picking_type_code(self):
        for point in self:
            if point.measure_on == 'move_line' and any(picking_type.code == 'repair_operation' for picking_type in point.picking_type_ids):
                raise UserError(_("The Quantity quality check type is not possible with repair operation types."))


class QualityCheck(models.Model):
    _inherit = "quality.check"

    repair_id = fields.Many2one('repair.order', 'Repair Order', check_company=True, index='btree_not_null')

    @api.depends('repair_id')
    def _compute_allowed_product_ids(self):
        for check in self:
            if check.repair_id:
                check.allowed_product_ids = check.repair_id.product_id
                continue
            super(QualityCheck, check)._compute_allowed_product_ids()

    @api.depends('repair_id')
    def _compute_hide_picking_id(self):
        for check in self:
            check.hide_picking_id = check._should_hide_picking_id()

    @api.depends('repair_id')
    def _compute_hide_production_id(self):
        for check in self:
            check.hide_production_id = check._should_hide_production_id()

    @api.depends('repair_id')
    def _compute_hide_repair_id(self):
        for check in self:
            check.hide_repair_id = check._should_hide_repair_id()

    @api.constrains('product_id', 'repair_id')
    def _check_allowed_product_ids_with_repair(self):
        for check in self:
            if check.product_id and check.repair_id and check.product_id != check.repair_id.product_id:
                raise ValidationError(_("%(product_name)s is not in Repair Order %(repair_name)s", product_name=check.product_id.name, repair_name=check.repair_id.name))

    def _should_hide_production_id(self):
        super_should_hide_production_id = super()._should_hide_production_id()
        if super_should_hide_production_id == -1:
            return -1
        if super_should_hide_production_id == 1 or bool(self.repair_id):
            return 1
        return 0

    def _should_hide_repair_id(self):
        if self.repair_id:
            return -1
        if super()._should_hide_repair_id() == 1 and not bool(self.repair_id):
            return 1
        return 0

    def _should_hide_picking_id(self):
        super_should_hide_picking_id = super()._should_hide_picking_id()
        if super_should_hide_picking_id == -1:
            return -1
        if super_should_hide_picking_id == 1 or bool(self.repair_id):
            return 1
        return 0


class QualityAlert(models.Model):
    _inherit = "quality.alert"

    repair_id = fields.Many2one('repair.order', "Repair Order", check_company=True, index='btree_not_null')
