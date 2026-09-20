from odoo import api, models
from odoo.exceptions import RedirectWarning
from odoo.tools.float_utils import float_compare, float_round


class AccountIntrastatGoodsReportHandler(models.AbstractModel):
    _inherit = 'account.intrastat.goods.report.handler'

    def _get_exporting_dict_data(self, result_dict, query_res):
        # Extends account_reports

        def format_number(key: str) -> str:
            if query_res.get(key):
                val = float(query_res[key])
                return (
                    "%0.3f" % float_round(val, 3)
                    if float_compare(val, 1.0, precision_digits=3) <= 0
                    else str(int(val))
                )
            return '0'

        super()._get_exporting_dict_data(result_dict, query_res)

        if self.env.company.account_fiscal_country_id.code != 'CZ':
            return result_dict

        if not self.env.company.vat:
            raise RedirectWarning(
                self.env._("The company VAT number is required to export Intrastat data."),
                self.env['ir.actions.act_window']._for_xml_id('base.action_res_company_form'),
                self.env._("Configure Company"),
            )

        result_dict.update({
            'intrastat_type': query_res['intrastat_type'][0],
            'region_code': '',  # needs to be empty
            'weight': format_number('weight'),
            'supplementary_units': format_number('supplementary_units'),
            'value': int(query_res['value']),
            'vat': self.env.company.vat,
            'code_of_movement': 'ST',  # see Code for a specific type or movement of goods
            'description_of_goods': '',  # It does not have to be filled out
            'statistical_sign': '',  # see Statistical code
        })
        return result_dict

    def cz_intrastat_export_to_csv(self, options):
        """ Exports a csv document containing the required intrastat data, compliant with the official format.
        """
        options['export_mode'] = 'file'
        report = self.env['account.report'].browse(options['report_id'])
        results = self._cz_intrastat_get_report_results_for_file_export(options)
        file_content = self._cz_intrastat_get_csv_file_content(results, options)
        return {
            'file_name': report.get_default_report_filename(options, 'csv'),
            'file_content': file_content,
            'file_type': 'csv',
        }

    @api.model
    def _cz_intrastat_get_report_results_for_file_export(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        expressions = report.line_ids.expression_ids
        report._init_currency_table(options)
        return self._report_custom_engine_intrastat(
            expressions,
            options,
            expressions[0].date_scope,
            'id',
            None,
        )

    @api.model
    def _cz_intrastat_get_csv_file_content(self, results, options):
        date_options = options.get('date', {})
        file_content = ''
        columns = [
            'vat',
            'intrastat_type',
            'partner_vat',
            'country_code',
            'region_code',
            'intrastat_product_origin_country_code',
            'transaction_code',
            'transport_code',
            'incoterm_code',
            'code_of_movement',
            'commodity_code',
            'statistical_sign',
            'description_of_goods',
            'weight',
            'supplementary_units',
            'value'
        ]

        reporting_month = date_options.get('date_from', '').split('-')[1] if date_options.get('date_from') else ''
        reporting_year = date_options.get('date_from', '').split('-')[0] if date_options.get('date_from') else ''

        for result in results:
            file_content += ';'.join([
                reporting_month,
                reporting_year,
                *(str(result[1].get(col) or '') for col in columns)
            ]) + ';;\n'

        return file_content
