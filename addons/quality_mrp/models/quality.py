# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class QualityPoint(models.Model):
    _inherit = "quality.point"

    @api.model
    def _get_domain_for_production(self, quality_points_domain):
        return quality_points_domain

    @api.onchange('measure_on', 'picking_type_ids')
    def _onchange_measure_on(self):
        # to remove in Master
        pass

    @api.constrains('measure_on', 'picking_type_ids')
    def _check_measure_on(self):
        for point in self:
            if point.measure_on == 'move_line' and any(pt.code == 'mrp_operation' for pt in point.picking_type_ids):
                raise UserError(_("The Quantity quality check type is not possible with manufacturing operation types."))


class QualityCheck(models.Model):
    _inherit = "quality.check"

    production_id = fields.Many2one(
        'mrp.production', 'Production Order', check_company=True)

    def do_fail(self):
        self.ensure_one()
        res = super().do_fail()
        if self.production_id and self.production_id.product_id.tracking == 'serial' and self.move_line_id:
            self.move_line_id.move_id.picked = False
        return res

    @api.depends('production_id')
    def _compute_allowed_product_ids(self):
        for check in self:
            if check.production_id:
                check.allowed_product_ids = check.production_id.move_finished_ids.product_id
                continue
            super(QualityCheck, check)._compute_allowed_product_ids()

    @api.depends('production_id')
    def _compute_hide_picking_id(self):
        for check in self:
            check.hide_picking_id = check._should_hide_picking_id()

    @api.depends('production_id')
    def _compute_hide_production_id(self):
        for check in self:
            check.hide_production_id = check._should_hide_production_id()

    @api.depends('production_id')
    def _compute_hide_repair_id(self):
        for check in self:
            check.hide_repair_id = check._should_hide_repair_id()

    @api.depends("production_id.qty_producing")
    def _compute_qty_line(self):
        record_without_production = self.env['quality.check']
        for qc in self:
            if qc.production_id:
                qc.qty_line = qc.production_id.qty_producing
            else:
                record_without_production |= qc
        return super(QualityCheck, record_without_production)._compute_qty_line()

    @api.constrains('product_id', 'production_id')
    def _check_allowed_product_ids_with_production(self):
        for check in self:
            if check.product_id and check.production_id and check.product_id not in check.production_id.move_finished_ids.product_id:
                raise ValidationError(_("%(product_name)s is not in Production Order %(production_name)s", product_name=check.product_id.name, production_name=check.production_id.name))

    def _can_move_to_failure_location(self):
        self.ensure_one()
        if self.production_id and self.quality_state == 'fail':
            return True
        return super()._can_move_to_failure_location()

    def _move_to_failure_location_operation(self, failure_location_id):
        self.ensure_one()
        if self.production_id and failure_location_id:
            self.production_id.move_finished_ids.location_dest_id = failure_location_id
            self.failure_location_id = failure_location_id
        return super()._move_to_failure_location_operation(failure_location_id)

    def _move_to_failure_location_product(self, failure_location_id):
        self.ensure_one()
        if self.production_id and failure_location_id:
            self.production_id.move_finished_ids.filtered(
                lambda m: m.product_id == self.product_id
            ).location_dest_id = failure_location_id
        self.failure_location_id = failure_location_id
        return super()._move_to_failure_location_product(failure_location_id)

    def _should_hide_production_id(self):
        if self.production_id:
            return -1
        if super()._should_hide_production_id() == 1 and not bool(self.production_id):
            return 1
        return 0

    def _should_hide_repair_id(self):
        super_should_hide_repair_id = super()._should_hide_repair_id()
        if super_should_hide_repair_id == -1:
            return -1
        if super_should_hide_repair_id == 1 or bool(self.production_id):
            return 1
        return 0

    def _should_hide_picking_id(self):
        super_should_hide_picking_id = super()._should_hide_picking_id()
        if super_should_hide_picking_id == -1:
            return -1
        if super_should_hide_picking_id == 1 or bool(self.production_id):
            return 1
        return 0


class QualityAlert(models.Model):
    _inherit = "quality.alert"

    production_id = fields.Many2one(
        'mrp.production', "Production Order", check_company=True)
