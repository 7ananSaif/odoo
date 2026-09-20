from odoo import models, _


class l10n_CoAccountTrialBalancePerPartnerReportHandler(models.AbstractModel):
    _name = 'l10n_co.account.trial.balance.per.partner.report.handler'
    _inherit = 'account.trial.balance.report.handler'
    _description = "Custom handler for Colombian 'Trial balance per partner'"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)

        options['columns'].insert(0, {
            'name': _('Partner VAT'),
            'column_group_key': options['columns'][-1]['column_group_key'],
            'expression_label': 'partner_vat',
            'sortable': False,
            'figure_type': 'string',
            'blank_if_zero': True,
        })
        options['column_headers'][0].insert(0, {'name': _('Partners information'), 'colspan': 1})

        xlsx_button_option = next((button_opt for button_opt in options['buttons'] if button_opt.get('action_param') == 'export_to_xlsx'), {})
        xlsx_button_option['action_param'] = 'l10n_co_export_to_xlsx'

    def l10n_co_export_to_xlsx(self, options):
        # Force the unfold_all attribute when exporting xlsx file
        options['unfold_all'] = True
        report = self.env['account.report'].browse(options['report_id'])
        return report.export_to_xlsx(options)

    def _custom_line_postprocessor(self, report, options, lines):
        partner_ids = {report._get_res_id_from_line_id(line['id'], 'res.partner') for line in lines}
        partners = self.env['res.partner'].search_fetch(domain=[('id', 'in', list(partner_ids))], field_names=['vat'])
        partner_vats = {partner.id: partner.vat or '' for partner in partners}

        filtered_lines = []
        for line in super()._custom_line_postprocessor(report, options, lines):
            partner_id = report._get_res_id_from_line_id(line['id'], 'res.partner')
            partner_vat = partner_vats.get(partner_id, '') if partner_id else ''
            line['columns'][0].update({'is_zero': False, 'no_format': partner_vat})
            filtered_lines.append(line)

        return filtered_lines
