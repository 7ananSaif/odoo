# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Domain


class QualityPoint(models.Model):
    _inherit = "quality.point"

    @api.model
    def _get_domain_for_production(self, quality_points_domain):
        quality_points_domain = super()._get_domain_for_production(quality_points_domain)
        return Domain.AND((quality_points_domain, Domain('operation_id', '=', False)))


    @api.constrains('operation_id', 'measure_frequency_type')
    def _check_measure_frequency_type(self):
        for point in self:
            if point.measure_frequency_type == 'on_demand' and self.operation_id:
                raise UserError(_("The On-demand frequency is not possible with work order quality points."))


class QualityCheck(models.Model):
    _inherit = "quality.check"

    operation_id = fields.Many2one(related="point_id.operation_id")

    def do_pass(self):
        self.ensure_one()
        super().do_pass()

    def do_fail(self):
        self.ensure_one()
        return super().do_fail()

    def do_measure(self):
        self.ensure_one()
        res = super().do_measure()
        if not self.workorder_id:
            return res
        next_res = self._next()
        if isinstance(next_res, dict):
            return next_res
        return {'next_check_id': self._next()}


    def _next(self):
        self.ensure_one()
        result = super()._next()
        if self.quality_state == 'fail' and (self.warning_message or self.failure_message):
            return {
                'name': _('Quality Check Failed'),
                'type': 'ir.actions.act_window',
                'res_model': 'quality.check.wizard',
                'views': [(self.env.ref('quality_control.quality_check_wizard_form_failure').id, 'form')],
                'target': 'new',
                'context': {
                    **self.env.context,
                    'default_check_ids': [self.id],
                    'default_current_check_id': self.id,
                    'default_test_type': self.test_type,
                    'default_failure_message': self.failure_message,
                    'default_warning_message': self.warning_message,
                },
                'next_check_id': result,
            }
        return result

    def _get_check_result(self):
        if self.test_type == 'passfail':
            return _('Success') if self.quality_state == 'pass' else _('Failure')
        elif self.test_type == 'measure':
            return '{} {}'.format(self.measure, self.norm_unit)
        return super(QualityCheck, self)._get_check_result()

    def _check_to_unlink(self):
        self.ensure_one()
        return super()._check_to_unlink() and not self.workorder_id

    def action_pass_and_next(self):
        self.ensure_one()
        super().do_pass()
        return {'next_check_id': self._next()}

    def action_fail_and_next(self):
        self.ensure_one()
        super().do_fail()
        return {'next_check_id': self._next()}
