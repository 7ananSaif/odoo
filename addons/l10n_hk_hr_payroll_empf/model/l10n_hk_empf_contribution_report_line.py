# Part of Odoo. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import RedirectWarning


class L10n_HkEMpfContributionReportLine(models.Model):
    _name = 'l10n_hk.empf.contribution.report.line'
    _description = 'eMPF contribution report line'
    _order = 'errors, employee_id, contribution_start_date'

    # ------------------
    # Fields declaration
    # ------------------

    report_id = fields.Many2one(comodel_name='l10n_hk.empf.contribution.report', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='report_id.company_id', store=True)
    report_contribution_start_date = fields.Date(related='report_id.contribution_period_start')
    report_contribution_end_date = fields.Date(related='report_id.contribution_period_end')
    report_scheme_id = fields.Many2one(related='report_id.scheme_id')

    currency_id = fields.Many2one(comodel_name='res.currency', related='company_id.currency_id')
    payslip_id = fields.Many2one(
        comodel_name='hr.payslip',
        domain="[('state', 'in', ['validated', 'paid']), ('company_id', '=', company_id), ('date_from', '>=', report_contribution_start_date), ('date_to', '<=', report_contribution_end_date), ('l10n_hk_version_scheme_id', '=', report_scheme_id), ('l10n_hk_contribution_line_id', '=', False)]"
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        related='payslip_id.employee_id',
        store=True,
        readonly=False,
        domain="[('company_id', '=', company_id), ('l10n_hk_mpf_scheme_id', '=', report_scheme_id), ('active', 'in', [True, False])]"
    )
    version_id = fields.Many2one(comodel_name='hr.version', compute='_compute_version_id', store=True, readonly=False)
    mpf_account_number = fields.Char(related='version_id.l10n_hk_mpf_account_number')

    contribution_start_date = fields.Date(related='payslip_id.date_from', store=True, readonly=False)
    contribution_end_date = fields.Date(related='payslip_id.date_to', store=True, readonly=False)
    status = fields.Selection(
        selection=[
            ('N', "New Member"),
            ('E', "Existing Member"),
            ('T', "Terminated Member"),
        ]
    )
    # Wages
    relevant_income = fields.Monetary(
        string="Relevant Income",
        compute='_compute_amounts',
        store=True,
        readonly=False,
    )
    basic_salary = fields.Monetary(
        string="Basic Salary",
        compute='_compute_amounts',
        store=True,
        readonly=False,
    )
    # Contributions
    eemc = fields.Monetary(
        compute='_compute_amounts',
        store=True,
        readonly=False,
    )
    ermc = fields.Monetary(
        compute='_compute_amounts',
        store=True,
        readonly=False,
    )
    eevc = fields.Monetary(
        compute='_compute_amounts',
        store=True,
        readonly=False,
    )
    ervc = fields.Monetary(
        compute='_compute_amounts',
        store=True,
        readonly=False,
    )
    ervc_2 = fields.Monetary(
        compute='_compute_amounts',
        store=True,
        readonly=False,
    )
    total_contributions = fields.Monetary(
        string="Contributions",
        help="Total amount of all contributions in the period.",
        compute='_compute_total',
        store=True,
    )
    # Surcharges
    employee_surcharge = fields.Monetary(
        string="Employee's Surcharge",
    )
    employer_surcharge = fields.Monetary(
        string="Employer's Surcharge",
    )
    # LSP/SP
    termination_payment_type = fields.Selection(
        selection=[
            ('L', "Long Service Payment"),
            ('S', "Severance Payment"),
        ],
        compute='_compute_termination_payment_type',
        store=True,
        readonly=False,
    )
    errors = fields.Char()

    # --------------------------------
    # Compute, inverse, search methods
    # --------------------------------

    @api.depends('payslip_id')
    def _compute_amounts(self):
        """ Compute the amount of all contributions in the period. """
        payslip_values = self.payslip_id._get_line_values(['BASIC', 'MPF_GROSS', 'EEMC', 'ERMC', 'EEVC', 'ERVC', 'ERVC2'])
        for line in self:
            code_to_field = (
                ('MPF_GROSS', 'relevant_income'),
                ('BASIC', 'basic_salary'),
            )
            # We only display contribution amounts if the "due date" was reached; otherwise we will display amounts that won't
            # show in the csv and this would lead to confusion
            if line._has_reached_due_date():
                code_to_field += (
                    ('EEMC', 'eemc'),
                    ('ERMC', 'ermc'),
                    ('EEVC', 'eevc'),
                    ('ERVC', 'ervc'),
                    ('ERVC2', 'ervc_2'),
                )
            for code, field in code_to_field:
                line[field] = abs(payslip_values[code][line.payslip_id.id]['total']) if line.payslip_id else line[field]

    @api.depends('eemc', 'ermc', 'eevc', 'ervc', 'ervc_2')
    def _compute_total(self):
        for line in self:
            line.total_contributions = line.eemc + line.ermc + line.eevc + line.ervc + line.ervc_2

    @api.depends('payslip_id', 'employee_id', 'contribution_start_date')
    def _compute_version_id(self):
        """
        Compute the version based on the provided information.
        By default, it uses the payslip's version but fallback on the employee if no payslip is set (manual line) in
        which case it will look for the version matching the contribution start date.
        """
        for line in self:
            if line.payslip_id:
                line.version_id = line.payslip_id.version_id
            elif line.employee_id:
                line.version_id = line.employee_id._get_version(line.contribution_start_date)
            else:
                line.version_id = False

    @api.depends('version_id', 'ermc', 'eemc', 'ervc', 'ervc_2', 'eevc')
    def _compute_termination_payment_type(self):
        """ Look for a payslip matching any of these, and use this information. """
        termination_payment_slips = self.env['hr.payslip']._read_group(
            domain=[
                ('state', 'in', ['paid', 'validated']),
                ('version_id', 'in', self.version_id.ids),
                ('structure_code', 'in', ['CAP57SEVERANCE', 'CAP57LONG']),
                ('net_wage', '!=', 0.0),
            ],
            groupby=['employee_id'],
            aggregates=['id:recordset'],
        )
        termination_payment_slips_dict = {employee: payslips.sorted() for employee, payslips in termination_payment_slips}
        for line in self:
            # Terminated employee without contributions cannot declare LSP/SP.
            # These can only be declared in the general upload file alongside the employee last month contribution.
            # But to be more flexible in case we missed something, we only check at computation and let users manually update
            # the type if needed before exporting to csv.
            any_contributions = any(
                amount != 0
                for amount in (line.ermc, line.eemc, line.ervc, line.ervc_2, line.eevc)
            )

            if line.status != 'T' or line.employee_id not in termination_payment_slips_dict or not any_contributions:
                line.termination_payment_type = False
                continue

            termination_slip = next(iter(termination_payment_slips_dict[line.employee_id]))
            line.termination_payment_type = 'L' if termination_slip.struct_id.code == 'CAP57LONG' else 'S'

    def _has_reached_due_date(self):
        """
        Return True if the employee has reached the due date for the first contribution payment,
        or if their contribution start setting is not set to at_due_date.
        """
        self.ensure_one()
        if not self.version_id:
            return False

        due_date = self.employee_id._get_first_version_date() + relativedelta(days=59)
        at_due_date = self.version_id.l10n_hk_mpf_contribution_start == 'at_due_date'
        reached_due_date = due_date.replace(day=1) <= self.report_id.contribution_period_end.replace(day=1)
        return not at_due_date or (at_due_date and reached_due_date)

    def action_display_errors(self):
        """
        In order to make managing errors easier, we have a button that will, when clicked, display all errors on the
        record as a redirect warning and redirect to the problematic record.

        The errors are validated when the user press validate on the report; and the button will show at that time.
        """
        self.ensure_one()

        if not self.errors:
            return  # The action shouldn't show in this case, but just in case

        error_messages = []
        error_checks = self.report_id._prepare_error_check_dict()
        for error in self.errors.split(','):
            error_messages.append(error_checks[error]['message'])

        action = self.version_id.action_open_version()
        action['target'] = 'new'

        raise RedirectWarning(
            message='\n'.join(error_messages),
            action=action,
            button_text=self.env._('Show Employee'),
        )
