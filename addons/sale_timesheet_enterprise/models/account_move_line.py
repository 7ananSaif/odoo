# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.fields import Domain
from odoo.addons.sale_timesheet_enterprise.models.sale_order_line import DEFAULT_INVOICED_TIMESHEET


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def _timesheet_domain_get_invoiced_lines(self, sale_line_delivery):
        domain = super()._timesheet_domain_get_invoiced_lines(sale_line_delivery)
        param_invoiced_timesheet = self.env['ir.config_parameter'].sudo().get_param('sale.invoiced_timesheet', DEFAULT_INVOICED_TIMESHEET)
        if param_invoiced_timesheet == 'approved':
            domain = Domain.AND([domain, [('validated', '=', True)]])
        return domain
