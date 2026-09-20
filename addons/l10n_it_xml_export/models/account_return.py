from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.fields import Domain
from odoo.tools import date_utils
from odoo.exceptions import UserError


class AccountReturn(models.Model):
    _inherit = 'account.return'
    is_quarter_month = fields.Boolean(compute='_compute_is_quarter_month')
    country_code = fields.Char(compute='_compute_country_code')

    @api.depends('company_id.country_id')
    def _compute_country_code(self):
        for record in self:
            record.country_code = record.company_id.country_id.code or False

    @api.depends('date_from')
    def _compute_is_quarter_month(self):
        for record in self:
            if record.date_from:
                month = record.date_from.month
                record.is_quarter_month = month in [3, 6, 9, 12]
            else:
                record.is_quarter_month = False

    def _compute_record_states_for_it(self, record):
        current_state = record.state
        visible_states = []
        active = True
        state_field = record.type_id.states_workflow

        for state, label in record._fields[state_field].selection:
            if (
                    state == 'submitted'
                    and record.country_code == 'IT'
                    and not record.is_quarter_month
            ):
                label = 'Close'

            if state == current_state:
                active = False

            if state != 'new':
                visible_states.append({
                    'active': active or state == current_state or record.is_completed,
                    'name': state,
                    'label': label,
                })

        record.visible_states = visible_states

    @api.depends('type_id', 'state', 'country_code', 'is_quarter_month')
    def _compute_visible_states(self):
        super()._compute_visible_states()

        for record in self:
            self._compute_record_states_for_it(record)

    def action_submit(self):
        """This action will be called by the POST button on a tax report account move.
           As posting this move will generate the XML report, it won't call `action_post`
           immediately, but will open the wizard that configures this XML file.
           Validating the wizard will resume the `action_post` and take these options in
           consideration when generating the XML report.
        """
        self.ensure_one()
        if self.country_code != "IT":
            return super().action_submit()

        super().action_submit()
        # The following process is only required if we are posting an Italian tax closing move.
        if (
            self.closing_move_ids
            and "l10n_it_xml_export_monthly_tax_report_options" not in self.env.context
            and self.is_quarter_month
        ):
            closing_max_date = max(self.closing_move_ids.mapped('date'))
            last_posted_tax_closing = self.env['account.move'].search(Domain([
                *self.env['account.move']._check_company_domain(self.company_id),
                ('closing_return_id', '!=', False),
                ('move_type', '=', 'entry'),
                ('state', '=', 'posted'),
                ('date', '<', closing_max_date),
            ]) & Domain.OR([
                Domain('fiscal_position_id.country_id.code', '=', 'IT'),
                Domain([
                    ('fiscal_position_id', '=', False),
                    ('company_id.account_fiscal_country_id.code', '=', 'IT'),
                ])
            ]), order='date desc', limit=1)
            if last_posted_tax_closing:
                # If there is a posted tax closing, we only check that there is no gap in the months.
                if closing_max_date.month - last_posted_tax_closing[0].date.month > 1:
                    raise UserError(_("You cannot post the tax closing of %(month)s without posting the previous month tax closing first.", month=closing_max_date.strftime("%m/%Y")))
            else:
                # If no tax closing has ever been posted, we have to check if there are Italian taxes in a previous month (meaning a missing tax closing).
                quarterly = self.env.company.account_return_periodicity == 'trimester'
                previous_move = self.env['account.move'].search_fetch(Domain([
                    *self.env['account.move']._check_company_domain(self.company_id),
                    ('closing_return_id', '=', False),
                    ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
                    ('date', '<', date_utils.start_of(closing_max_date, 'quarter' if quarterly else 'month')),
                ]) & Domain.OR([
                    Domain('fiscal_position_id.country_id.code', '=', 'IT'),
                    Domain([
                        ('fiscal_position_id', '=', False),
                        ('company_id.account_fiscal_country_id.code', '=', 'IT'),
                    ])
                ]), order='date asc', field_names=['date'], limit=1)
                if previous_move:
                    report = self.env.ref('l10n_it.tax_monthly_report_vat')
                    current = previous_move.date.replace(day=1)
                    while current <= closing_max_date.replace(day=1):
                        date_from = date_utils.start_of(current, 'month')
                        date_to = date_utils.end_of(current, 'month')
                        at_date_options = report.get_options({
                            'selected_variant_id': report.id,
                            'date': {
                                'date_from': date_from,
                                'date_to': date_to,
                                'mode': 'range',
                                'filter': 'custom',
                            },
                        })
                        at_date_report_lines = report._get_lines(at_date_options)
                        balance_col_idx = next((idx for idx, col in enumerate(at_date_options.get('columns', [])) if col.get('expression_label') == 'balance'), None)
                        if any(line['columns'][balance_col_idx]['no_format'] for line in at_date_report_lines if line['name'].startswith('VP')):
                            raise UserError(_("You cannot post the tax closing of that month because older months have taxes to report but no tax closing posted. Oldest month is %(month)s", month=current.strftime("%m/%Y")))
                        current += relativedelta(months=1)

            # If the process has not been stopped yet, we open the wizard for the xml export.
            view_id = self.env.ref('l10n_it_xml_export.monthly_tax_report_xml_export_wizard_view').id
            ctx = self.env.context.copy()
            ctx.update({
                'l10n_it_moves_to_post': self.ids,
                'l10n_it_xml_export_monthly_tax_report_options': {
                    'date': {'date_to': closing_max_date},
                },
            })

            return {
                'name': _('Post a tax report entry'),
                'view_mode': 'form',
                'views': [[view_id, 'form']],
                'res_model': 'l10n_it_xml_export.monthly.tax.report.xml.export.wizard',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'context': ctx,
            }
