# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import OrderedSet
from odoo.tools.float_utils import float_is_zero


class StockPicking(models.Model):
    _inherit = "stock.picking"

    check_ids = fields.One2many('quality.check', 'picking_id', 'Checks')
    quality_check_todo = fields.Boolean('Pending checks', compute='_compute_check', search='_search_quality_check_todo')
    quality_check_fail = fields.Boolean(compute='_compute_check')
    quality_alert_ids = fields.One2many('quality.alert', 'picking_id', 'Alerts')
    quality_alert_count = fields.Integer(compute='_compute_quality_alert_count')

    def _compute_check(self):
        for picking in self:
            todo = False
            fail = False
            # Only prefetch needed QC fields to avoid to bloat the cache by fetching other QC data.
            checks = picking.check_ids
            checks.fetch(['quality_state'])
            for check in checks:
                if check.quality_state == 'none':
                    todo = True
                elif check.quality_state == 'fail':
                    fail = True
                if fail and todo:
                    break
            picking.quality_check_fail = fail
            picking.quality_check_todo = todo

    def _search_quality_check_todo(self, operator, value):
        if operator != 'in':
            return NotImplemented

        domain = [('picking_id', '!=', False), ('quality_state', '=', 'none')]
        query_check_picking = self.env['quality.check']._search(domain)
        return [('id', 'in', query_check_picking.subselect('picking_id'))]

    def _compute_quality_alert_count(self):
        for picking in self:
            picking.quality_alert_count = len(picking.quality_alert_ids)

    def _checks_to_do(self):
        check_ids_to_do = OrderedSet()
        for picking in self:
            has_picked = True
            if all(not move.picked for move in picking.move_ids):
                checkable_lines = picking.move_line_ids
                has_picked = False
            else:
                checkable_lines = picking.move_line_ids.filtered(
                    lambda ml: ml._is_checkable(check_picked=has_picked)
                )
            checkable_products = checkable_lines.product_id
            checks_to_do = self.check_ids.filtered(
                lambda qc: qc._is_to_do(checkable_products, check_picked=has_picked)
            )
            check_ids_to_do.update(checks_to_do.ids)
        return self.env['quality.check'].browse(check_ids_to_do)

    def check_quality(self):
        checks = self._checks_to_do()
        if checks:
            return checks.action_open_quality_check_wizard()
        return True

    def _create_backorder(self, backorder_moves=None):
        res = super(StockPicking, self)._create_backorder(backorder_moves=backorder_moves)
        if self.env.context.get('skip_check'):
            return res
        for backorder in res:
            # Do not link the QC of move lines with quantity of 0 in backorder.
            backorder.move_line_ids.filtered(lambda ml: not float_is_zero(ml.quantity, precision_rounding=ml.product_uom_id.rounding)).check_ids.picking_id = backorder
            if backorder.backorder_id.state in ('done', 'cancel'):
                backorder.backorder_id.check_ids.filtered(lambda qc: qc.quality_state == 'none').sudo().unlink()
            backorder.move_ids._create_quality_checks()
        return res

    def _action_done(self):
        if self._check_for_quality_checks():
            raise UserError(_('You still need to do the quality checks!'))
        return super(StockPicking, self)._action_done()

    def _pre_action_done_hook(self):
        res = super()._pre_action_done_hook()
        if res is True:
            return self.with_context(picking_validation=True).check_quality()
        return res

    def _check_for_quality_checks(self):
        quality_pickings = self.env['stock.picking']
        for picking in self:
            if picking._checks_to_do():
                quality_pickings |= picking
        return quality_pickings

    def action_cancel(self):
        res = super(StockPicking, self).action_cancel()
        self.sudo().mapped('check_ids').filtered(lambda x: x.quality_state == 'none').unlink()
        return res

    def action_open_quality_check_picking(self):
        action = self.env["ir.actions.actions"]._for_xml_id("quality_control.quality_check_action_picking")
        action['context'] = self.env.context.copy()
        action['context'].update({
            'search_default_picking_id': [self.id],
            'default_picking_id': self.id,
            'show_lots_text': self.show_lots_text,
        })
        return action

    def action_open_on_demand_quality_check(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("quality_control.quality_check_action_main")
        action['views'] = [(False, 'form')]
        action['context'] = {
            **self.env.context,
            'default_product_id': self.product_id.id if len(self.move_ids.ids) == 1 else False,
            'default_product_tmpl_id': self.move_ids.product_tmpl_id.ids,
            'default_picking_id': self.id,
        }
        return action

    def button_quality_alert(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("quality_control.quality_alert_action_check")
        action['views'] = [(False, 'form')]
        action['context'] = {
            'default_product_id': self.product_id.id,
            'default_product_tmpl_id': self.product_id.product_tmpl_id.id,
            'default_picking_id': self.id,
        }
        return action

    def open_quality_alert_picking(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("quality_control.quality_alert_action_check")
        action['context'] = {
            'default_product_id': self.product_id.id,
            'default_product_tmpl_id': self.product_id.product_tmpl_id.id,
            'default_picking_id': self.id,
        }
        action['domain'] = [('id', 'in', self.quality_alert_ids.ids)]
        action['views'] = [(False, 'list'), (False, 'form')]
        if self.quality_alert_count == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = self.quality_alert_ids.id
        return action
