from dateutil.relativedelta import relativedelta

from odoo import _, api, models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        # Extends account_reports
        if return_type_external_id == 'l10n_dk_reports.dk_tax_return_type' and not return_type.with_company(company).deadline_days_delay:
            periodicity = return_type._get_periodicity(company)
            if periodicity == 'trimester':
                return date_to + relativedelta(months=+3, day=1)
            elif periodicity == 'year':
                end_of_year = date_to + relativedelta(month=12, day=31)
                return end_of_year + relativedelta(months=+3, day=1)
            else:
                return date_to + relativedelta(days=25)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

    def action_submit(self):
        # Extends account_reports
        if self.type_external_id == 'l10n_dk_reports.dk_ec_sales_list_return_type':
            return self.env['l10n_dk_reports.ec.sales.list.submission.wizard']._open_submission_wizard(self)

        if self.type_external_id == 'l10n_dk_reports.dk_tax_return_type':
            wizard = self.env['l10n_dk_reports.tax.report.calendar.wizard'].create({
                'report_id': self.type_id.report_id.id,
                'company_id': self.env.company.id,
                'date_from': self.date_from,
                'date_to': self.date_to,
            })
            return wizard._get_records_action(
                name=_('Tax Report RSU Calendar'),
                target='new',
            )

        return super().action_submit()
