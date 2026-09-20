# Part of Odoo. See LICENSE file for full copyright and licensing details.
from math import sqrt
from dateutil.relativedelta import relativedelta
from datetime import datetime

import random

from odoo import api, Command, models, fields, _
from odoo.fields import Domain
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_round, SQL
from odoo.exceptions import ValidationError


class QualityPoint(models.Model):
    _inherit = "quality.point"
    _rec_names_search = ["name", "title"]

    failure_message = fields.Html('Failure Message')
    measure_on = fields.Selection([
        ('operation', 'Operation'),
        ('product', 'Product'),
        ('move_line', 'Quantity')], string="Control per", default='product', required=True,
        help="""Operation = One quality check is requested at the operation level.
                  Product = A quality check is requested per product.
                 Quantity = A quality check is requested for each new product quantity registered, with partial quantity checks also possible.""")
    measure_frequency_type = fields.Selection([
        ('all', 'All'),
        ('random', 'Randomly'),
        ('periodical', 'Periodically'),
        ('on_demand', 'On-demand')], string="Control Frequency",
        default='all', required=True)
    measure_frequency_value = fields.Float('Percentage', help="The probability of each quality check being generated")  # TDE RENAME ?
    measure_frequency_unit_value = fields.Integer('Frequency Unit Value')  # TDE RENAME ?
    measure_frequency_unit = fields.Selection([
        ('day', 'Days'),
        ('week', 'Weeks'),
        ('month', 'Months')], default="day")  # TDE RENAME ?
    is_lot_tested_fractionally = fields.Boolean(string="Lot Tested Fractionally", help="Determines if only a fraction of the lot should be tested",
                                                compute="_compute_is_lot_tested_fractionally")
    testing_percentage_within_lot = fields.Float(help="Defines the percentage within a lot that should be tested", default=100)
    norm = fields.Float('Norm', digits='Quality Tests')  # TDE RENAME ?
    tolerance_min = fields.Float('Min Tolerance', digits='Quality Tests')
    tolerance_max = fields.Float('Max Tolerance', digits='Quality Tests')
    norm_unit = fields.Char('Norm Unit', default=lambda self: 'mm')  # TDE RENAME ?
    average = fields.Float(compute="_compute_standard_deviation_and_average")
    standard_deviation = fields.Float(compute="_compute_standard_deviation_and_average")
    spreadsheet_template_id = fields.Many2one(
        'quality.spreadsheet.template',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    spreadsheet_check_cell = fields.Char(
        related="spreadsheet_template_id.check_cell",
        readonly=False,
    )

    @api.depends('name', 'title')
    def _compute_display_name(self):
        for point in self:
            point.display_name = f'{point.name} - {point.title}' if point.title else point.name

    @api.depends('testing_percentage_within_lot')
    def _compute_is_lot_tested_fractionally(self):
        for point in self:
            point.is_lot_tested_fractionally = point.testing_percentage_within_lot < 100

    def _compute_standard_deviation_and_average(self):
        # The variance and mean are computed by the Welford’s method and used the Bessel's
        # correction because are working on a sample.
        for point in self:
            if point.test_type != 'measure':
                point.average = 0
                point.standard_deviation = 0
                continue
            mean = 0.0
            s = 0.0
            n = 0
            for check in point.check_ids.filtered(lambda x: x.quality_state != 'none'):
                n += 1
                delta = check.measure - mean
                mean += delta / n
                delta2 = check.measure - mean
                s += delta * delta2

            if n > 1:
                point.average = mean
                point.standard_deviation = sqrt( s / ( n - 1))
            elif n == 1:
                point.average = mean
                point.standard_deviation = 0.0
            else:
                point.average = 0.0
                point.standard_deviation = 0.0

    @api.onchange('norm')
    def onchange_norm(self):
        if self.tolerance_max == 0.0:
            self.tolerance_max = self.norm

    def check_execute_now(self):
        self.ensure_one()
        if self.measure_frequency_type == 'all':
            return True
        elif self.measure_frequency_type == 'random':
            return (random.random() < self.measure_frequency_value / 100.0)
        elif self.measure_frequency_type == 'periodical':
            delta = False
            if self.measure_frequency_unit == 'day':
                delta = relativedelta(days=self.measure_frequency_unit_value)
            elif self.measure_frequency_unit == 'week':
                delta = relativedelta(weeks=self.measure_frequency_unit_value)
            elif self.measure_frequency_unit == 'month':
                delta = relativedelta(months=self.measure_frequency_unit_value)
            date_previous = datetime.today() - delta
            has_checks = bool(self.env['quality.check'].search_count([
                ('point_id', '=', self.id),
                ('create_date', '>=', date_previous.strftime(DEFAULT_SERVER_DATETIME_FORMAT))], limit=1))
            return not has_checks
        return super(QualityPoint, self).check_execute_now()

    def _get_type_default_domain(self):
        domain = super(QualityPoint, self)._get_type_default_domain()
        domain.append(('technical_name', '=', 'passfail'))
        return domain

    def action_see_quality_checks(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("quality_control.quality_check_action_main")
        action['domain'] = [('point_id', '=', self.id)]
        action['context'] = {
            'default_company_id': self.company_id.id,
            'default_point_id': self.id
        }
        return action

    def action_see_spc_control(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("quality_control.quality_check_action_spc")
        if self.test_type == 'measure':
            action['context'] = {'group_by': ['name', 'point_id'], 'graph_measure': ['measure'], 'graph_mode': 'line'}
        action['domain'] = [('point_id', '=', self.id), ('quality_state', '!=', 'none')]
        return action

    def _get_checks_values(self, products, company_id, existing_checks=False):
        quality_points_list = []
        point_values = []
        if not existing_checks:
            existing_checks = []
        for check in existing_checks:
            point_key = (check.point_id.id, check.team_id.id, check.product_id.id)
            quality_points_list.append(point_key)

        for point in self:
            if not point.check_execute_now():
                continue
            point_products = point.product_ids

            if point.product_category_ids:
                point_product_from_categories = self.env['product.product'].search([('categ_id', 'child_of', point.product_category_ids.ids), ('id', 'in', products.ids)])
                point_products |= point_product_from_categories

            if not point.product_ids and not point.product_category_ids:
                point_products |= products

            for product in point_products:
                if product not in products:
                    continue
                point_key = (point.id, point.team_id.id, product.id)
                if point_key in quality_points_list:
                    continue
                point_values.append({
                    'point_id': point.id,
                    'measure_on': point.measure_on,
                    'team_id': point.team_id.id,
                    'product_id': product.id,
                    'company_id': company_id,
                })
                quality_points_list.append(point_key)

        return point_values

    @api.model
    def _get_domain(self, product_ids, picking_type_id, measure_on=False, on_demand=False):
        """ Helper that returns a domain for quality.point based on the products and picking type
        pass as arguments. It will search for quality point having:
        - No product_ids and no product_category_id
        - At least one variant from product_ids
        - At least one category that is a parent of the product_ids categories

        :param product_ids: the products that could require a quality check
        :type product_ids: :class:`~odoo.addons.product.models.product.ProductProduct`
        :param picking_type_id: the products that could require a quality check
        :type picking_type_id: :class:`~odoo.addons.stock.models.stock_picking.StockPickingType`
        :returns: the domain for quality point with given picking_type_id for all the product_ids
        """
        domain = Domain('picking_type_ids', 'in', picking_type_id.ids)
        domain_in_products_or_categs = Domain('product_ids', 'in', product_ids.ids) | Domain('product_category_ids', 'parent_of', product_ids.categ_id.ids)
        domain_no_products_and_categs = Domain('product_ids', '=', False) & Domain('product_category_ids', '=', False)
        domain &= domain_in_products_or_categs | domain_no_products_and_categs
        if measure_on:
            domain &= Domain('measure_on', '=', measure_on)
        domain &= Domain('measure_frequency_type', '=' if on_demand else '!=', 'on_demand')
        return domain


class QualityCheck(models.Model):
    _inherit = "quality.check"

    product_id = fields.Many2one(
        compute='_compute_product_id',
        store=True, readonly=False)

    lot_ids = fields.Many2many(
        compute='_compute_lot_ids',
        store=True, readonly=False)

    failure_message = fields.Html(related='point_id.failure_message', readonly=True)
    measure = fields.Float('Measure', default=0.0, digits='Quality Tests', tracking=True)
    measure_success = fields.Selection([
        ('none', 'No measure'),
        ('pass', 'Pass'),
        ('fail', 'Fail')], string="Measure Success", compute="_compute_measure_success",
        readonly=True, store=True)
    tolerance_min = fields.Float('Min Tolerance', related='point_id.tolerance_min', readonly=True)
    tolerance_max = fields.Float('Max Tolerance', related='point_id.tolerance_max', readonly=True)
    warning_message = fields.Text(compute='_compute_warning_message')
    norm_unit = fields.Char(related='point_id.norm_unit', readonly=True)
    qty_to_test = fields.Float(compute="_compute_qty_to_test", string="Quantity to Test", help="Quantity of product to test within the lot", digits='Product Unit')
    qty_tested = fields.Float(string="Quantity Tested", help="Quantity of product tested within the lot", digits='Product Unit')
    measure_on = fields.Selection([
        ('operation', 'Operation'),
        ('product', 'Product'),
        ('move_line', 'Quantity')], string="Control per", default='product', required=True,
        compute="_compute_measure_on", store=True,
        help="""Operation = One quality check is requested at the operation level.
                  Product = A quality check is requested per product.
                 Quantity = A quality check is requested for each new product quantity registered, with partial quantity checks also possible.""")
    move_line_id = fields.Many2one(
        "stock.move.line",
        "Stock Move Line",
        check_company=True,
        help="In case of Quality Check by Quantity, Move Line on which the Quality Check applies",
        index="btree_not_null",
    )
    lot_name = fields.Char('Lot/Serial Number Name', related='move_line_id.lot_name')
    lot_line_id = fields.Many2one('stock.lot', store=True, compute='_compute_lot_line_id')
    qty_line = fields.Float(compute='_compute_qty_line', string="Quantity")
    qty_passed = fields.Float('Quantity Passed', help="Quantity of product that passed the quality check", compute='_compute_qty_passed', store=True)
    qty_failed = fields.Float('Quantity Failed', help="Quantity of product that failed the quality check", compute='_compute_qty_failed', store=True)
    uom_id = fields.Many2one(related='product_id.uom_id', string="Unit")
    show_lot_text = fields.Boolean(compute='_compute_show_lot_text')
    is_lot_tested_fractionally = fields.Boolean(related='point_id.is_lot_tested_fractionally')
    testing_percentage_within_lot = fields.Float(related="point_id.testing_percentage_within_lot")
    product_tracking = fields.Selection(related='product_id.tracking')
    spreadsheet_id = fields.Many2one(
        'quality.check.spreadsheet',
        domain="[('company_id', 'in', company_ids)]",
    )
    allowed_product_ids = fields.Many2many('product.product', compute='_compute_allowed_product_ids')
    spreadsheet_template_id = fields.Many2one(
        'quality.spreadsheet.template',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        store=True, copy=True, compute='_compute_spreadsheet_template_id',
    )
    hide_picking_id = fields.Integer(compute='_compute_hide_picking_id')
    hide_production_id = fields.Integer(compute='_compute_hide_production_id')
    hide_repair_id = fields.Integer(compute='_compute_hide_repair_id')

    @api.depends('picking_id')
    def _compute_allowed_product_ids(self):
        for check in self:
            check.allowed_product_ids = False
            if check.picking_id:
                check.allowed_product_ids = check.picking_id.move_ids.product_id

    @api.depends('picking_id')
    def _compute_hide_picking_id(self):
        for check in self:
            check.hide_picking_id = check._should_hide_picking_id()

    @api.depends('picking_id')
    def _compute_hide_production_id(self):
        for check in self:
            check.hide_production_id = check._should_hide_production_id()

    @api.depends('picking_id')
    def _compute_hide_repair_id(self):
        for check in self:
            check.hide_repair_id = check._should_hide_repair_id()

    @api.depends('point_id')
    def _compute_spreadsheet_template_id(self):
        for check in self:
            if check.point_id and check.point_id.spreadsheet_template_id:
                check.spreadsheet_template_id = check.point_id.spreadsheet_template_id

    @api.depends('point_id')
    def _compute_measure_on(self):
        for check in self:
            if check.point_id:
                check.measure_on = check.point_id.measure_on

    @api.depends('measure_on')
    def _compute_product_id(self):
        for check in self:
            if check.measure_on == 'operation':
                check.product_id = False

    @api.depends('measure_on')
    def _compute_lot_ids(self):
        for check in self:
            if check.measure_on == 'operation':
                check.lot_ids = False

    @api.depends('measure_success')
    def _compute_warning_message(self):
        for rec in self:
            if rec.measure_success == 'fail':
                rec.warning_message = _('You measured %(measure).2f %(unit)s and it should be between %(tolerance_min).2f and %(tolerance_max).2f %(unit)s.',
                    measure=rec.measure, unit=rec.norm_unit, tolerance_min=rec.point_id.tolerance_min,
                    tolerance_max=rec.point_id.tolerance_max,
                )
            else:
                rec.warning_message = ''

    @api.depends('move_line_id.quantity')
    def _compute_qty_line(self):
        for qc in self:
            qc.qty_line = qc.move_line_id.quantity

    @api.depends('qty_line', 'quality_state')
    def _compute_qty_passed(self):
        for qc in self:
            if qc.quality_state == 'pass':
                qc.qty_passed = qc.qty_line
            else:
                qc.qty_passed = 0

    @api.depends('qty_line', 'quality_state')
    def _compute_qty_failed(self):
        for qc in self:
            if qc.quality_state == 'fail':
                qc.qty_failed = qc.qty_line
            else:
                qc.qty_failed = 0

    @api.depends('move_line_id.lot_id')
    def _compute_lot_line_id(self):
        for qc in self:
            qc.lot_line_id = qc.move_line_id.lot_id
            if qc.lot_line_id and qc._update_lot_from_lot_line():
                qc.lot_ids = qc.lot_line_id

    def _update_lot_from_lot_line(self):
        return True

    @api.depends('measure')
    def _compute_measure_success(self):
        for rec in self:
            if rec.point_id.test_type == 'passfail':
                rec.measure_success = 'none'
            else:
                if rec.measure < rec.point_id.tolerance_min or rec.measure > rec.point_id.tolerance_max:
                    rec.measure_success = 'fail'
                else:
                    rec.measure_success = 'pass'

    # Add picture dependency
    @api.depends('picture')
    def _compute_result(self):
        super(QualityCheck, self)._compute_result()

    @api.depends('qty_line', 'testing_percentage_within_lot', 'is_lot_tested_fractionally')
    def _compute_qty_to_test(self):
        for qc in self:
            if qc.is_lot_tested_fractionally:
                qc.qty_to_test = float_round(qc.qty_line * qc.testing_percentage_within_lot / 100, precision_rounding=qc.product_id.uom_id.rounding or 0.01, rounding_method="UP")
            else:
                qc.qty_to_test = qc.qty_line

    @api.depends('lot_line_id', 'move_line_id')
    def _compute_show_lot_text(self):
        for qc in self:
            if qc.lot_line_id or not qc.move_line_id:
                qc.show_lot_text = False
            else:
                qc.show_lot_text = True

    @api.constrains('product_id', 'picking_id')
    def _check_allowed_product_ids_with_picking(self):
        for check in self:
            if check.product_id and check.picking_id and check.product_id not in check.picking_id.move_ids.product_id:
                raise ValidationError(_("%(product_name)s is not in Picking %(picking_name)s", product_name=check.product_id.name, picking_name=check.picking_id.name))

    def _should_hide_production_id(self):
        return 1 if bool(self.picking_id) else 0

    def _should_hide_repair_id(self):
        return 1 if bool(self.picking_id) else 0

    def _should_hide_picking_id(self):
        return -1 if bool(self.picking_id) else 0

    def _is_pass_fail_applicable(self):
        if self.test_type in ['passfail', 'measure']:
            return True
        return super()._is_pass_fail_applicable()

    def _get_check_result(self):
        if self.test_type == 'picture' and self.picture:
            return _('Picture Uploaded')
        else:
            return super(QualityCheck, self)._get_check_result()

    def _check_to_unlink(self):
        return True

    def _measure_passes(self):
        self.ensure_one()
        return self.point_id.tolerance_min <= self.measure <= self.point_id.tolerance_max

    def do_measure(self):
        self.ensure_one()
        if self._measure_passes():
            return self.do_pass()
        else:
            return self.do_fail()

    def do_alert(self):
        self.ensure_one()
        alert = self.env['quality.alert'].create({
            'check_id': self.id,
            'product_id': self.product_id.id,
            'product_tmpl_id': self.product_id.product_tmpl_id.id,
            'lot_ids': self.lot_ids.ids,
            'user_id': self.user_id.id,
            'team_id': self.team_id.id,
            'company_id': self.company_id.id
        })
        return {
            'name': _('Quality Alert'),
            'type': 'ir.actions.act_window',
            'res_model': 'quality.alert',
            'views': [(self.env.ref('quality_control.quality_alert_view_form').id, 'form')],
            'res_id': alert.id,
            'context': {'default_check_id': self.id},
        }

    def action_see_alerts(self):
        self.ensure_one()
        if len(self.alert_ids) == 1:
            return {
                'name': _('Quality Alert'),
                'type': 'ir.actions.act_window',
                'res_model': 'quality.alert',
                'views': [(self.env.ref('quality_control.quality_alert_view_form').id, 'form')],
                'res_id': self.alert_ids.ids[0],
                'context': {'default_check_id': self.id},
            }
        else:
            action = self.env["ir.actions.actions"]._for_xml_id("quality_control.quality_alert_action_check")
            action['domain'] = [('id', 'in', self.alert_ids.ids)]
            action['context'] = dict(self.env.context, default_check_id=self.id)
            return action

    def action_open_quality_check_wizard(self, current_check_id=None):
        check_ids = sorted(self.ids)
        action = self.env["ir.actions.actions"]._for_xml_id("quality_control.action_quality_check_wizard")
        check_id = self.browse(current_check_id or check_ids[0])
        action['name'] = check_id._get_check_action_name()
        action['context'] = self.env.context.copy()
        action['context'].update({
            'default_check_ids': check_ids,
            'default_current_check_id': check_id.id,
            'default_qty_tested': check_id.qty_to_test,
        })
        return action

    def action_open_spreadsheet(self):
        if not self.spreadsheet_id:
            self.spreadsheet_id = self._create_spreadsheet_from_template()
        action = self.spreadsheet_id.action_open_spreadsheet()
        action['params']['check_id'] = self.id
        return action

    def _create_spreadsheet_from_template(self):
        self.ensure_one()
        spreadsheet_template = self.spreadsheet_template_id
        spreadsheet = self.env['quality.check.spreadsheet'].create({
            'name': spreadsheet_template.name,
            'spreadsheet_data': spreadsheet_template.spreadsheet_data,
            'check_cell': self.point_id.spreadsheet_check_cell,
        })
        spreadsheet.spreadsheet_snapshot = spreadsheet_template.spreadsheet_snapshot
        spreadsheet_template._copy_revisions_to(spreadsheet)
        return spreadsheet

    def unlink(self):
        if self.spreadsheet_id:
            self.spreadsheet_id.unlink()
        return super().unlink()

    def _can_move_to_failure_location(self):
        self.ensure_one()
        return self.quality_state == 'fail' and self.picking_id

    def _move_to_failure_location(self, failure_location_id, failed_qty=None):
        """ This function is used to fail move lines and can optionally:
             - split it into failed and passed qties (i.e. 2 moves w/1 check each)
             - send the failed qty to a failure location
        :param failure_location_id: id of location to send failed qty to
        :param failed_qty: qty failed on check, defaults to None, if None all quantity of the move is failed
        """
        for check in self:
            if not check._can_move_to_failure_location():
                continue
            match check.measure_on:
                case 'operation':
                    if not failure_location_id:
                        return
                    check._move_to_failure_location_operation(failure_location_id)
                case 'product':
                    if not failure_location_id:
                        return
                    check._move_to_failure_location_product(failure_location_id)
                case 'move_line':
                    if not failed_qty:
                        check.do_pass()
                        return
                    move_line = check.move_line_id
                    move = move_line.move_id
                    dest_location = failure_location_id or move_line.location_dest_id.id
                    if failed_qty == move_line.quantity:
                        move_line.location_dest_id = dest_location
                        if move_line.quantity == move.quantity:
                            move.location_dest_id = dest_location
                        else:
                            move.with_context(do_not_unreserve=True).product_uom_qty -= failed_qty
                            move.copy({
                                'location_dest_id': dest_location,
                                'move_orig_ids': move.move_orig_ids,
                                'product_uom_qty': failed_qty,
                                'state': 'assigned',
                                'move_line_ids': [Command.link(move_line.id)],
                            })
                        check.failure_location_id = dest_location
                        return
                    move.with_context(do_not_unreserve=True).product_uom_qty -= min(failed_qty, move_line.quantity)
                    move_line.quantity -= min(failed_qty, move_line.quantity)
                    failed_move_line = move_line.with_context(default_check_ids=None, no_checks=True).copy({
                        'location_dest_id': dest_location,
                        'quantity': failed_qty,
                    })
                    move.copy({
                        'location_dest_id': dest_location,
                        'move_orig_ids': move.move_orig_ids,
                        'product_uom_qty': min(failed_qty, move_line.quantity),
                        'state': 'assigned',
                        'move_line_ids': [Command.link(failed_move_line.id)],
                    })
                    # switch the checks, check in self should always be the failed one,
                    # new check linked to original move line will be passed check
                    new_check = check.create(failed_move_line._get_check_values(check.point_id))
                    check.move_line_id = failed_move_line
                    new_check.move_line_id = move_line
                    new_check.qty_tested = 0
                    new_check.do_pass()
                    check.failure_location_id = dest_location
                case _:
                    return

    def _move_to_failure_location_operation(self, failure_location_id):
        self.ensure_one()
        if self.picking_id and failure_location_id:
            self.picking_id.move_ids.location_dest_id = failure_location_id
            self.failure_location_id = failure_location_id

    def _move_to_failure_location_product(self, failure_location_id):
        self.ensure_one()
        if self.picking_id and failure_location_id:
            self.picking_id.move_ids.filtered(
                lambda m: m.product_id == self.product_id
            ).location_dest_id = failure_location_id
        self.failure_location_id = failure_location_id

    def _get_check_action_name(self):
        self.ensure_one()
        action_name = self.title or "Quality Check"
        if self.product_id:
            action_name += ' : %s' % self.product_id.display_name
        if self.qty_line and self.uom_id:
            action_name += ' - %s %s' % (self.qty_line, self.uom_id.name)
        if self.lot_name or self.lot_line_id or self.lot_ids:
            action_name += ' - %s' % (self.lot_name or self.lot_line_id.name or self.lot_ids.name)
        return action_name

    def _get_type_default_domain(self):
        domain = super()._get_type_default_domain()
        domain.append(('technical_name', '=', 'passfail'))
        return domain

    def _is_to_do(self, checkable_products, check_picked=False):
        self.ensure_one()
        if self.quality_state != 'none':
            return False
        if self.measure_on != 'operation':
            if self.product_id not in checkable_products:
                return False
            if self.move_line_id:
                if not self.move_line_id._is_checkable(check_picked):
                    return False
        # Only process qc related to tracked product if its lot is set
        if self.move_line_id and self.product_id.tracking in ["serial", "lot"]:
            if self.move_line_id.picking_type_use_create_lots or self.move_line_id.picking_type_use_existing_lots:
                if not self.move_line_id.lot_id and not self.move_line_id.lot_name:
                    return False
        return True


class QualityAlert(models.Model):
    _inherit = "quality.alert"

    title = fields.Char('Title')

    def action_see_check(self):
        return {
            'name': _('Quality Check'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'quality.check',
            'target': 'current',
            'res_id': self.check_id.id,
        }

    @api.depends('name', 'title')
    def _compute_display_name(self):
        for record in self:
            name = record.name + ' - ' + record.title if record.title else record.name
            record.display_name = name

    @api.model
    def name_create(self, name):
        """ Create an alert with name_create should use prepend the sequence in the name """
        record = self.create({
            'title': name,
        })
        return record.id, record.display_name

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        # We need to add the name in custom_values or it will use the subject.
        custom_values['name'] = self.env['ir.sequence'].next_by_code('quality.alert') or _('New')
        if msg_dict.get('subject'):
            custom_values['title'] = msg_dict['subject']
        if msg_dict.get('body'):
            custom_values['description'] = msg_dict['body']
        return super(QualityAlert, self).message_new(msg_dict, custom_values)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    quality_control_point_qty = fields.Integer(compute='_compute_quality_check_qty', groups='quality.group_quality_user')
    quality_pass_qty = fields.Integer(compute='_compute_quality_check_qty', groups='quality.group_quality_user')
    quality_fail_qty = fields.Integer(compute='_compute_quality_check_qty', groups='quality.group_quality_user')

    @api.depends('product_variant_ids')
    def _compute_quality_check_qty(self):
        for product_tmpl in self:
            product_tmpl.quality_fail_qty, product_tmpl.quality_pass_qty = product_tmpl.product_variant_ids._count_quality_checks()
            product_tmpl.quality_control_point_qty = product_tmpl.with_context(active_test=product_tmpl.active).product_variant_ids._count_quality_points()

    def action_see_quality_control_points(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("quality_control.quality_point_action")
        action['context'] = dict(self.env.context, default_product_ids=self.product_variant_ids.ids)

        action['views'] = [(self.env.ref("quality.quality_point_view_tree").id, 'list'), (False, 'form'), (False, 'kanban')]
        domain_in_products_or_categs = ['|', ('product_ids', 'in', self.product_variant_ids.ids), ('product_category_ids', 'parent_of', self.categ_id.ids)]
        domain_no_products_and_categs = [('product_ids', '=', False), ('product_category_ids', '=', False)]
        action['domain'] = Domain.OR([domain_in_products_or_categs, domain_no_products_and_categs])
        return action

    def action_see_quality_checks(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("quality_control.quality_check_action_main")
        action['context'] = dict(self.env.context, default_product_id=self.product_variant_id.id, create=False)
        action['domain'] = [
            '|',
                ('product_id', 'in', self.product_variant_ids.ids),
                '&',
                    ('measure_on', '=', 'operation'),
                    ('picking_id.move_ids.product_tmpl_id', '=', self.id),
        ]
        return action


class ProductProduct(models.Model):
    _inherit = "product.product"

    quality_control_point_qty = fields.Integer(compute='_compute_quality_check_qty', groups='quality.group_quality_user')
    quality_pass_qty = fields.Integer(compute='_compute_quality_check_qty', groups='quality.group_quality_user')
    quality_fail_qty = fields.Integer(compute='_compute_quality_check_qty', groups='quality.group_quality_user')

    def _compute_quality_check_qty(self):
        for product in self:
            product.quality_fail_qty, product.quality_pass_qty = product._count_quality_checks()
            product.quality_control_point_qty = product._count_quality_points()

    def _count_quality_checks(self):
        quality_fail_qty = 0
        quality_pass_qty = 0
        domain = [
            '|',
                ('product_id', 'in', self.ids),
                '&',
                    ('measure_on', '=', 'operation'),
                    ('picking_id.move_ids.product_id', 'in', self.ids),
            ('company_id', '=', self.env.company.id),
            ('quality_state', '!=', 'none')
        ]
        quality_checks_by_state = self.env['quality.check']._read_group(domain, ['quality_state'], ['__count'])
        for quality_state, count in quality_checks_by_state:
            if quality_state == 'fail':
                quality_fail_qty = count
            elif quality_state == 'pass':
                quality_pass_qty = count

        return quality_fail_qty, quality_pass_qty

    def _count_quality_points(self):
        """ Compute the count of all related quality points, which means quality points that have either
        the product in common, a product category parent of this product's category or no product/category
        set at all.
        """
        query = self.env['quality.point']._search([('company_id', '=', self.env.company.id)])

        additional_where_clause = self._additional_quality_point_where_clause()
        if additional_where_clause:
            query.add_where(additional_where_clause)

        parent_category_ids = [int(parent_id) for parent_id in self.categ_id.parent_path.split('/')[:-1]] if self.categ_id else []
        query.add_where(SQL(
            """(
                    (
                        -- QP has at least one linked product and one is right
                        EXISTS (SELECT 1 FROM product_product_quality_point_rel rel WHERE rel.quality_point_id = quality_point.id AND rel.product_product_id = ANY(%s))
                        -- Or QP has at least one linked product category and one is right
                        OR EXISTS (SELECT 1 FROM product_category_quality_point_rel rel WHERE rel.quality_point_id = quality_point.id AND rel.product_category_id = ANY(%s))
                    )
                    OR (
                        -- QP has no linked products
                        NOT EXISTS (SELECT 1 FROM product_product_quality_point_rel rel WHERE rel.quality_point_id = quality_point.id)
                        -- And QP has no linked product categories
                        AND NOT EXISTS (SELECT 1 FROM product_category_quality_point_rel rel WHERE rel.quality_point_id = quality_point.id)
                    )
                )
            """,
            self.ids, parent_category_ids,
        ))
        rows = self.env.execute_query(query.select("COUNT(*)"))
        return rows[0][0]

    def action_see_quality_control_points(self):
        self.ensure_one()
        action = self.product_tmpl_id.action_see_quality_control_points()
        action['context'].update(default_product_ids=self.ids)

        domain_in_products_or_categs = ['|', ('product_ids', 'in', self.ids), ('product_category_ids', 'parent_of', self.categ_id.ids)]
        domain_no_products_and_categs = [('product_ids', '=', False), ('product_category_ids', '=', False)]
        action['domain'] = Domain.OR([domain_in_products_or_categs, domain_no_products_and_categs])
        return action

    def action_see_quality_checks(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("quality_control.quality_check_action_main")
        action['context'] = dict(self.env.context, default_product_id=self.id, create=False)
        action['domain'] = [
            '|',
                ('product_id', '=', self.id),
                '&',
                    ('measure_on', '=', 'operation'),
                    ('picking_id.move_ids.product_id', '=', self.id),
        ]
        return action

    def _additional_quality_point_where_clause(self) -> SQL:
        return SQL()
