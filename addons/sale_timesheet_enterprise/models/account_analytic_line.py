# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.fields import Domain
from odoo.addons.sale_timesheet_enterprise.models.sale_order_line import DEFAULT_INVOICED_TIMESHEET


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    def _compute_display_timer(self):
        invoiced_timesheets = self.filtered('timesheet_invoice_id')
        invoiced_timesheets.display_timer = False
        super(AccountAnalyticLine, self - invoiced_timesheets)._compute_display_timer()

    @api.depends('validated')
    def _compute_so_line(self):
        updatable_timesheets = self.filtered(lambda t: t._is_updatable_timesheet())
        super(AccountAnalyticLine, updatable_timesheets)._compute_so_line()

    @api.model
    def grid_update_cell(self, domain, measure_field_name, value):
        return super().grid_update_cell(
            Domain.AND([domain, [('timesheet_invoice_id', '=', False)]]),
            measure_field_name,
            value,
        )

    def _is_updatable_timesheet(self):
        return super()._is_updatable_timesheet() and not self.validated

    def _get_last_timesheet_domain(self):
        """ Do not update the timesheet which are already linked with invoice """
        domain = super()._get_last_timesheet_domain()
        return Domain.AND([domain, [
            '|', ('timesheet_invoice_id', '=', False),
            ('timesheet_invoice_id.state', '=', 'cancel')
        ]])

    def _should_not_display_timer(self):
        self.ensure_one()
        return super()._should_not_display_timer() or self.timesheet_invoice_id

    def _timesheet_get_portal_domain(self):
        domain = super()._timesheet_get_portal_domain()
        param_invoiced_timesheet = self.env['ir.config_parameter'].sudo().get_param('sale.invoiced_timesheet', DEFAULT_INVOICED_TIMESHEET)
        if param_invoiced_timesheet == 'approved':
            domain = Domain.AND([domain, [('validated', '=', True)]])
        return domain

    def _compute_can_validate(self):
        # Prevent `user_can_validate` from being true if the line is validated and the SO aswell
        billed_lines = self.filtered(lambda l: l.validated and not l._is_not_billed())
        for line in billed_lines:
            line.user_can_validate = False
        self -= billed_lines
        return super()._compute_can_validate()

    def action_invalidate_timesheet(self):
        invoice_validated_timesheets = self.filtered(lambda l: not l._is_not_billed())
        self -= invoice_validated_timesheets
        # Errors are handled in the parent if there are no lines left
        return super().action_invalidate_timesheet()
