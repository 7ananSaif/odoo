# Part of Odoo. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta
import re

from odoo import api, fields, models


class KpiProvider(models.AbstractModel):
    _inherit = 'kpi.provider'

    @api.model
    def get_account_reports_kpi_summary(self):
        external_ids = {
            (imd.model, imd.res_id): imd.complete_name
            for imd in self.env['ir.model.data'].search([
                ('model', 'in', ['account.report', 'account.return.type']),
                ('module', '!=', '__export__'),
            ])
        }

        tax_returns = self.env['account.return'].search([
            '|', ('is_completed', '=', False), ('date_deadline', '>=', fields.Date.context_today(self)),
        ], order='date_deadline')

        def tax_return_get_name(tax_return):
            report_id = tax_return.type_id.report_id
            return report_id.name if report_id else tax_return.type_id.name

        def tax_return_grouping_key(tax_return):
            external_id = ''

            # Determine the external identifier used to categorize the tax returns:
            # - use the identifier of the root report if any,
            # - otherwise use the identifier of the report,
            # - otherwise use the identifier of the return type.
            report_id = tax_return.type_id.report_id
            root_report_id = report_id.root_report_id
            external_id = external_ids.get((root_report_id._name, root_report_id.id))
            if not external_id:
                external_id = external_ids.get((report_id._name, report_id.id))
            if not external_id:
                external_id = external_ids.get((tax_return.type_id._name, tax_return.type_id.id))
            if not external_id:
                external_id = tax_return_get_name(tax_return)

            # Special case for l10n_eu_oss_reports.* that are all merged together.
            if external_id.startswith('l10n_eu_oss_reports.'):
                external_id = 'l10n_eu_oss_reports'

            # property names must match odoo.orm.utils.regex_alphanumeric
            return re.sub(r'[^a-z0-9_]', '_', external_id.lower())

        def tax_returns_get_value(tax_returns):
            today = fields.Date.context_today(self)
            for tax_return in tax_returns:
                if tax_return.date_deadline <= today:
                    return 'late'
                elif not tax_return.is_completed:
                    if tax_return.state in ('reviewed', 'submitted'):
                        return 'to_submit'
                    elif tax_return.date_deadline <= today + relativedelta(months=3):
                        return 'to_do'
                    else:
                        return 'longterm'
            return 'done'

        return [{
            'id': f'account_return.{external_id}',
            'name': tax_return_get_name(tax_returns[0]),
            'type': 'return_status',
            'value': tax_returns_get_value(tax_returns),
        } for external_id, tax_returns in tax_returns.grouped(tax_return_grouping_key).items()]

    @api.model
    def get_kpi_summary(self):
        result = super().get_kpi_summary()
        result.extend(self.get_account_reports_kpi_summary())
        return result
