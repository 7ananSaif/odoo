# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import date_utils
from odoo.tools.misc import format_date


class L10n_Ph_ReportsDatFileExport(models.TransientModel):
    _name = 'l10n_ph_reports.dat.file.export'
    _description = "Philippine Periodic VAT Report Export Wizard"

    attachment_for = fields.Selection(
        selection=[
            ('1601EQ', '1601EQ'),  # QAP - quarterly
            ('1604E', '1604E'),  # QAP - annually
            ('1701Q', '1701Q'),  # SAWT - quarterly
            ('1701', '1701'),  # SAWT - annually
            ('1702Q', '1702Q'),  # SAWT - quarterly
            ('1702', '1702'),  # SAWT - annually
            ('S', 'Summary Lists of Sales'),  # The key matches what is needed in the file
            ('P', 'Summary Lists of Purchases'),  # Samesies
        ],
        compute='_compute_attachment_for',
        readonly=False,
        store=True,
    )
    available_forms = fields.Char(
        default='1601EQ,1604E,1701Q,1701,1702Q,1702,S,P',  # default to all forms, provide the specific ones at creation.
    )
    dat_export_warning = fields.Json(compute='_compute_dat_export_warning')

    @api.depends('available_forms')
    def _compute_attachment_for(self):
        for wizard in self:
            wizard.attachment_for = wizard.available_forms and wizard.available_forms.split(',')[0]

    @api.depends('attachment_for')
    def _compute_dat_export_warning(self):
        for wizard in self:
            report_options = wizard.env.context.get('l10n_ph_reports_generation_options')
            if not report_options:
                wizard.dat_export_warning = False
                continue

            date_data = report_options['date']
            date_to = fields.Date.to_date(date_data['date_to'])
            period_types_display_map = {
                'fiscalyear': wizard.env._("the year %(year)s", year=date_data['string']),
                'quarter': wizard.env._("the Q%(quarter_number)s %(year)s", quarter_number=date_utils.get_quarter_number(date_to), year=date_to.year),
                'month': format_date(env=wizard.env, value=date_to, date_format='MMMM YYYY'),
                'custom': wizard.env._("%(date_from)s to %(date_to)s", date_from=date_data['date_from'], date_to=date_data['date_to']),
            }
            period_type = date_data['period_type']
            expected_period = False

            if wizard.attachment_for in {'1601EQ', '1701Q', '1702Q', 'S', 'P'} and period_type != 'quarter':
                expected_period = wizard.env._("a quarterly")
            elif wizard.attachment_for in {'1604E', '1701', '1702'} and period_type != 'fiscalyear':
                expected_period = wizard.env._("an annual")

            wizard.dat_export_warning = {
                'warning_mismatch_export_periodicity': {
                    'message': wizard.env._(
                        "Please note that the %(report_name)s is %(expected_period)s report, but you are exporting it for %(period)s.\n"
                        "You can change the export period using the date filter on the accounting report.",
                        report_name=dict(wizard._fields['attachment_for'].selection)[wizard.attachment_for],
                        expected_period=expected_period,
                        period=period_types_display_map[period_type],
                    ),
                    'level': 'warning',
                }
            } if expected_period else False

    def action_export_dat(self):
        self.ensure_one()
        if not self.attachment_for:
            raise UserError(self.env._("Please select which form you are exporting the attachment for."))

        if self.attachment_for in ['1601EQ', '1604E']:
            alpha_type = 'QAP'
            periodicity = 'quarterly' if self.attachment_for == '1601EQ' else 'annually'
            filename_date_format = '%m%Y' if periodicity == 'quarterly' else '%m%d%Y'
        elif self.attachment_for in ['1701', '1702']:
            alpha_type = 'SAWT'
            periodicity = 'annually'
            filename_date_format = '%m%Y'
        elif self.attachment_for in ['1701Q', '1702Q']:
            alpha_type = 'SAWT'
            periodicity = 'quarterly'
            filename_date_format = '%m%Y'
        else:
            alpha_type = 'SLSP'
            periodicity = 'quarterly'
            filename_date_format = '%m%Y'

        options = self.env.context.get('l10n_ph_reports_generation_options')
        options.update({
           'alpha_type': alpha_type,
           'form_type_code': self.attachment_for,
           'periodicity': periodicity,
           'filename_date_format': filename_date_format,
        })

        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'export_report_to_dat',
            },
        }
