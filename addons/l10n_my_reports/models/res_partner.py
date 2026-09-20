# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields
from odoo.fields import Domain


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_print_report_statement_account(self, options=None):
        domain = Domain.TRUE
        if options:
            date_to = options.get("date", {}).get("date_to", fields.Date.today())
            domain &= Domain(self.env['account.report']._get_options_account_type_domain(options))
        else:
            date_to = fields.Date.today()
        domain &= Domain('date', '<=', date_to)
        return self.env.ref('l10n_my_reports.action_report_statement_account').report_action(self, data={
            'date_to': date_to,
            'domain': domain,
        })
