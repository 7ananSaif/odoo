from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None):
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)
        if not main_company.is_northern_irish():
            return rslt

        return_type = self.env.ref('l10n_uk_intrastat.uk_intrastat_goods_return_type')
        company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, return_type.report_id)
        report = self.env.ref('account_intrastat.intrastat_report').with_context(allowed_company_ids=company_ids.ids)
        report_handler = self.env[report.custom_handler_model_name]
        offset = return_type._get_periodicity_months_delay(main_company)
        date_in_previous_period = fields.Date.context_today(self) - relativedelta(months=offset)
        date_from, date_to = return_type._get_period_boundaries(main_company, date_in_previous_period)
        options = {
            'date': {
                'date_from': fields.Date.to_string(date_from),
                'date_to': fields.Date.to_string(date_to),
                'filter': 'custom',
                'mode': 'range',
            },
            'selected_variant_id': return_type.report_id.id,
            'sections_source_id': return_type.report_id.id,
            'tax_unit': 'company_only' if not tax_unit else tax_unit.id,
            'intrastat_type': [
                {'name': _('Arrival'), 'selected': True, 'id': 'arrival'},
                {'name': _('Dispatch'), 'selected': False, 'id': 'dispatch'},
            ],
        }

        # Does arrival entries (imports) exceed the threshold of £500,000?
        arrival_options = report.get_options(previous_options=options)
        amount = report_handler._report_custom_engine_intrastat(None, arrival_options, None, None, None)['value']
        if amount >= 500_000:
            return_type._try_create_return_for_period(date_from, main_company, tax_unit)
            return rslt

        # Does dispatched entries (exports) exceed the threshold of £250,000?
        options['intrastat_type'][0]['selected'] = False
        options['intrastat_type'][1]['selected'] = True
        dispatch_options = report.get_options(previous_options=options)
        amount = report_handler._report_custom_engine_intrastat(None, dispatch_options, None, None, None)['value']
        if amount >= 250_000:
            return_type._try_create_return_for_period(date_from, main_company, tax_unit)

        return rslt
