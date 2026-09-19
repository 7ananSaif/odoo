# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class L10n_PhSlsReportHandler(models.AbstractModel):
    _name = 'l10n_ph.sls.report.handler'
    _inherit = ['l10n_ph.slsp.report.handler']
    _description = 'Summary Lists of Sales Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options.update({
            'journal_type': 'sale',
            # This mapping will be used to build the amount for each expression_label based on the grid names.
            'report_grids_map': {
                'exempt_amount': ['33A'],
                'zero_rated_amount': ['32A'],
                'taxable_amount': ['31A'],
                'tax_amount': ['31B'],
            }
        })

    # ================
    # .DAT file export
    # ================

    def _get_available_form_to_export(self):
        return 'S'

    def _get_dat_file_name(self, options):
        company = self.env["res.company"].browse(options["companies"][0]["id"])
        company_vat, _company_branch = self._get_partner_vat_branch(company.partner_id)
        date_to = self._get_report_date_to(options)
        return_period = date_to.strftime(options['filename_date_format'])

        return f"{company_vat}S{return_period}.dat"

    def _slsp_get_header_values(self, categories_summed_amount, options):
        company = self.env["res.company"].browse(options["companies"][0]["id"])
        company_vat, _company_branch = self._get_partner_vat_branch(company.partner_id)
        date_to = self._get_report_date_to(options)

        address_1, address_2 = self._get_partner_address_lines(company)

        return [
            'H',
            'S',
            self._format_value(company_vat, 9),
            self._format_value(company.partner_id.name, 50, quote=True),
            self._format_value(company.partner_id.last_name, 30, quote=True),
            self._format_value(company.partner_id.first_name, 30, quote=True),
            self._format_value(company.partner_id.middle_name, 30, quote=True),
            self._format_value(company.partner_id.name, 50, quote=True),
            self._format_value(address_1, 300, quote=True),
            self._format_value(address_2, 300, quote=True),
            self._format_value(categories_summed_amount.get('exempt_amount', 0.0), 14),
            self._format_value(categories_summed_amount.get('zero_rated_amount', 0.0), 14),
            self._format_value(categories_summed_amount.get('taxable_amount', 0.0), 14),
            self._format_value(categories_summed_amount.get('tax_amount', 0.0), 14),
            self._format_value(company.partner_id.l10n_ph_rdo or '', 3),
            self._format_value(date_to.strftime('%m/%d/%Y'), 10),
        ]

    def _slsp_get_line_values(self, line, options):
        company = self.env["res.company"].browse(options["companies"][0]["id"])
        company_vat, _company_branch = self._get_partner_vat_branch(company.partner_id)
        date_to = self._get_report_date_to(options)

        payee = self.env['res.partner'].browse(line.get('payee_id'))
        payee_vat, _payee_branch = self._get_partner_vat_branch(payee.commercial_partner_id)
        address_1, address_2 = self._get_partner_address_lines(payee)

        return [
            'D',
            'S',
            self._format_value(payee_vat, 9),
            self._format_value(line.get('payee_registered_name', ''), 50, quote=True),
            self._format_value(line.get('payee_last_name', ''), 30, quote=True),
            self._format_value(line.get('payee_first_name', ''), 30, quote=True),
            self._format_value(line.get('payee_middle_name', ''), 30, quote=True),
            self._format_value(address_1, 300, quote=True),
            self._format_value(address_2, 300, quote=True),
            self._format_value(line.get('exempt_amount', 0.0), 14),
            self._format_value(line.get('zero_rated_amount', 0.0), 14),
            self._format_value(line.get('taxable_amount', 0.0), 14),
            self._format_value(line.get('tax_amount', 0.0), 14),
            self._format_value(company_vat, 9),
            self._format_value(date_to.strftime('%m/%d/%Y'), 10),
        ]
