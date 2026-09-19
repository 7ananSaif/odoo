# Part of Odoo. See LICENSE file for full copyright and licensing details.
import csv
import io
import re

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.addons.phone_validation.tools import phone_validation
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command, Domain
from odoo.tools import date_utils


class L10n_HkEMpfContributionReport(models.Model):
    _name = 'l10n_hk.empf.contribution.report'
    _description = 'eMPF contribution report'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ------------------
    # Fields declaration
    # ------------------

    name = fields.Char(
        compute='_compute_name',
        store=True,
        readonly=False,
    )
    state = fields.Selection(
        string="State",
        selection=[
            ('draft', "Draft"),
            ('validated', "Validated"),
        ],
        default='draft',
        readonly=True,
        copy=False,
        tracking=True,
    )
    company_id = fields.Many2one(comodel_name='res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(comodel_name='res.currency', related='company_id.currency_id')
    scheme_id = fields.Many2one(
        string="Scheme",
        comodel_name='l10n_hk.mpf.scheme',
        domain="[('employer_account_number', '!=', False)]",
        required=True,
        compute='_compute_scheme_details',
        precompute=True,
        store=True,
        readonly=False,
    )
    payroll_group_id = fields.Many2one(
        string="Payroll Group",
        comodel_name='l10n_hk.payroll.group',
        domain="[('company_id', '=', company_id), ('scheme_id', '=', scheme_id)]",
        compute='_compute_scheme_details',
        precompute=True,
        store=True,
        readonly=False,
    )
    contribution_period_start = fields.Date(
        required=True,
        compute='_compute_period',
        precompute=True,
        store=True,
        readonly=False,
    )
    contribution_period_end = fields.Date(
        required=True,
        compute='_compute_period',
        precompute=True,
        store=True,
        readonly=False,
    )
    contribution_line_ids = fields.One2many(
        string="Contribution Lines",
        comodel_name='l10n_hk.empf.contribution.report.line',
        inverse_name='report_id',
        compute='_compute_contribution_lines',
        precompute=True,
        store=True,
        readonly=False,
    )

    payslip_run_id = fields.Many2one(
        comodel_name='hr.payslip.run',
        domain="[('company_id', '=', company_id), ('l10n_hk_payroll_empf_report_id', '=', False)]",
    )
    payslip_run_scheme_id = fields.Many2one(
        string="Payslip Run Scheme",
        related='payslip_run_id.l10n_hk_payroll_scheme_id',
    )
    payslip_run_group_id = fields.Many2one(
        string="Payslip Run Group",
        related='payslip_run_id.l10n_hk_payroll_group_id',
    )

    # Technically, this relationship is a one2one
    _payslip_run_id_uniq = models.UniqueIndex(
        '(payslip_run_id)',
        "A payslip run cannot be linked to multiple eMPF reports.",
    )

    # ----------------------------
    # Onchange, Constraint methods
    # ----------------------------

    @api.constrains('contribution_line_ids')
    def _contraints_avoid_overlap(self):
        """ Check the lines to avoid having two lines for the same employee overlapping. """
        for report in self:
            for employee, lines in report.contribution_line_ids.grouped('employee_id').items():
                if len(lines) < 2:
                    continue

                for line in lines:
                    for other in lines - line:
                        if max(line.contribution_start_date, other.contribution_start_date) <= min(line.contribution_end_date, other.contribution_end_date):
                            raise UserError(self.env._('Two report lines for a same employee cannot have overlapping contribution periods.'))

    # --------------------------------
    # Compute, inverse, search methods
    # --------------------------------

    @api.depends('contribution_period_start', 'contribution_period_end', 'scheme_id', 'payroll_group_id')
    def _compute_name(self):
        for report in self:
            period_string = report._get_period_string()
            if report.payroll_group_id:
                report.name = f"{report.scheme_id.name} - {report.payroll_group_id.name} - {period_string}"
            elif report.scheme_id:
                report.name = f"{report.scheme_id.name} - {period_string}"
            else:
                report.name = period_string

    @api.depends('payslip_run_id')
    def _compute_period(self):
        """ The period is expected to match the payrun, if one is set. Otherwise, default to the last month. """
        for report in self:
            report.contribution_period_start = report.payslip_run_id.date_start or fields.Date.today() - relativedelta(months=1, day=1)
            report.contribution_period_end = report.payslip_run_id.date_end or fields.Date.today() - relativedelta(months=1, day=31)

    @api.depends('payslip_run_id')
    def _compute_scheme_details(self):
        """ The scheme and group is expected to match the payrun, if one is set. """
        for report in self.filtered('payslip_run_id'):
            if report.payslip_run_id.l10n_hk_payroll_group_id:
                report.payroll_group_id = report.payslip_run_id.l10n_hk_payroll_group_id
                report.scheme_id = report.payslip_run_id.l10n_hk_payroll_group_id.scheme_id
            elif report.payslip_run_id.l10n_hk_payroll_scheme_id:
                report.scheme_id = report.payslip_run_id.l10n_hk_payroll_scheme_id

    @api.depends('scheme_id', 'payroll_group_id', 'payslip_run_id', 'contribution_period_start', 'contribution_period_end')
    def _compute_contribution_lines(self):
        """ We never recompute lines for  """
        for report in self:
            report._create_contribution_lines()

    # --------------
    # Action methods
    # --------------

    def action_validate(self):
        """
        Mark the report as validated, and make the fields "read-only".
        This will also process pending changes to the employee information regarding MPF, such as marking newly registered
        employee as registered, ...
        """
        self.ensure_one()
        # Assert all at once for all files, if an action is returned (notification) we do not want to go through with
        # the state change just yet
        action = self._assert_report_values()

        if action:
            return action

        self.state = 'validated'
        new_register_line = self.contribution_line_ids.filtered(lambda line: line.status == 'N')
        termination_line = self.contribution_line_ids.filtered(lambda line: line.status == 'T')
        new_register_line.version_id.l10n_hk_mpf_registration_status = 'registered'
        termination_line.version_id.l10n_hk_mpf_registration_status = 'terminated'

    def action_draft(self):
        """
        Mark the report as draft, and revert the changes done to the employees in the validate method.
        """
        self.ensure_one()
        self.state = 'draft'
        new_register_line = self.contribution_line_ids.filtered(lambda line: line.status == 'N')
        termination_line = self.contribution_line_ids.filtered(lambda line: line.status == 'T')
        new_register_line.version_id.l10n_hk_mpf_registration_status = 'next_contribution'
        termination_line.version_id.l10n_hk_mpf_registration_status = 'registered'

    def action_generate_report(self):
        """ Generate and download the CSV file following the eMPF specifications. """
        self.ensure_one()
        # Unlink any existing exports, we do not need to keep track of past submissions.
        existing_reports = self.env['ir.attachment'].search([('res_id', '=', self.id), ('res_model', '=', 'l10n_hk.empf.contribution.report')])
        if existing_reports:
            existing_reports.unlink()

        all_lines = self.contribution_line_ids
        new_employees_contribution_line_ids = all_lines.filtered(
            lambda line: line.status == "N" and not line.total_contributions
        )
        regular_contribution_line_ids = all_lines.filtered(
            lambda line: line.status == "E" or line.total_contributions
        )
        terminated_employees_contribution_line_ids = all_lines.filtered(
            lambda line: line.status == "T" and not line.total_contributions
        )
        lines_and_label = [
            (new_employees_contribution_line_ids, 'new_employees'),
            (regular_contribution_line_ids, 'contributions'),
            (terminated_employees_contribution_line_ids, 'terminated_employees'),
        ]

        reports_data = []
        for lines, label in lines_and_label:
            if not lines:
                continue

            csv_lines = []
            for line in lines.sorted():
                csv_lines.append((
                    *self._prepare_general_information(line),
                    *self._prepare_member_contribution_information(line),
                    *self._prepare_new_member_information(line),
                    *self._prepare_termination_of_member_information(line),
                ))

            with io.StringIO(newline="") as output:
                writer = csv.writer(output)
                for line_data in csv_lines:
                    writer.writerow(line_data)
                raw_file = output.getvalue().encode()

            if self.payroll_group_id:
                file_name = f"eMPF_{self.scheme_id.registration_number}_{self.payroll_group_id.group_id}_{self.contribution_period_end.strftime('%Y%m%d')}_{label}.csv"
            else:
                file_name = f"eMPF_{self.scheme_id.registration_number}_{self.contribution_period_end.strftime('%Y%m%d')}_{label}.csv"

            reports_data.append({
                'res_id': self.id,
                'res_model': 'l10n_hk.empf.contribution.report',
                'name': file_name,
                'type': 'binary',
                'raw': raw_file,
                'mimetype': 'text/csv',
            })

        attachments = self.env['ir.attachment'].create(reports_data)

        return {
            'type': 'ir.actions.act_url',
            'url': f'/l10n_hk_hr_payroll_empf/download_empf_report/{",".join(map(str, attachments.ids))}',
            'close': True,
        }

    def action_recompute_contribution_lines(self):
        for report in self.filtered(lambda r: r.state == 'draft'):
            report._create_contribution_lines()

    # -----------------------
    # CRUD, inherited methods
    # -----------------------

    @api.ondelete(at_uninstall=False)
    def _unlink_except_draft(self):
        """ Small constraints to help avoid mistakes. """
        for report in self:
            if report.state != 'draft':
                raise UserError(self.env._("You cannot delete a validated report. You must first set it to draft."))

    # ----------------
    # Business methods
    # ----------------

    def _assert_report_values(self):
        """
        The eMPF report validation/error solving is in two steps.
        When the validate button is pressed, we will execute this logic which will:
            - Run a series of validations on the lines
            - Saves any errors happening on each individual lines, as a comma-separated list of code in a char field.
            - And show a notification in case of errors to warn about them

        If errors are saved on the lines, they will display a button in the view that triggers step two:
            - User press the button, and we display a redirect warning listing the errors
            - The warning contains an action opening the record view in a modal allowing to fix easily

        This should allow users to easily navigate complex configuration errors without needing to keep changing screens/...

        :return: In case of errors, a notification warning about these.
        """
        self.ensure_one()

        # High level check, it doesn't make sense to continue further.
        if not self.contribution_line_ids:
            raise ValidationError(self.env._("You cannot export a CSV for an empty report."))

        # Prefetch the fields that we will use in the checks now, as the check mechanism will not prefetch properly and would query for each individual lines.
        self.contribution_line_ids.fetch(['status', 'version_id', 'employee_id', 'termination_payment_type'])
        self.contribution_line_ids.version_id.fetch(['identification_id', 'passport_id', 'departure_reason_id', 'department_id'])
        self.contribution_line_ids.version_id.departure_reason_id.fetch(['l10n_hk_empf_code'])
        self.contribution_line_ids.version_id.department_id.fetch(['name'])
        self.contribution_line_ids.employee_id.fetch(
            ['private_email', 'private_phone', 'birthday', 'l10n_hk_surname', 'l10n_hk_given_name', 'l10n_hk_name_in_chinese', 'company_country_code']
        )
        self.contribution_line_ids.employee_id.country_id.fetch(['code'])

        error_checks = self._prepare_error_check_dict()
        any_errors = False

        for line in self.contribution_line_ids:
            line_errors = []

            for error_code, error_details in error_checks.items():
                if error_details['check'](line):
                    line_errors.append(error_code)

            line.errors = ','.join(line_errors) if line_errors else None
            if not any_errors and line_errors:
                any_errors = True

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Validation Failed',
                'message': 'Please take a look at the Report Lines for more details.',
                'type': 'danger',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},  # To display the error buttons
            }
        } if any_errors else None

    def _get_period_string(self):
        """ Return a string representing the period, formatted to match the group schedule (if any) """
        self.ensure_one()
        date_start = self.contribution_period_start
        date_end = self.contribution_period_end
        if not self.payroll_group_id:
            return f"{date_start.strftime('%d %b %Y')} -> {date_end.strftime('%d %b %Y')}"
        match self.payroll_group_id.contribution_frequency:
            case 'monthly':
                return f"{date_end.strftime('%b %Y')}"
            case 'quarterly':
                quarter_number = date_utils.get_quarter_number(date_end)
                return f"Q{quarter_number} {date_end.strftime('%Y')}"
            case 'biweekly':
                return f"{date_start.strftime('%d %b %Y')} -> {date_end.strftime('%d %b %Y')}"
            case 'weekly':
                return f"{date_start.strftime('%d %b %Y')} -> {date_end.strftime('%d %b %Y')}"
            case 'semi-monthly':
                # Semi-monthly shouldn't be between two months, so we can shorten it.
                return f"{date_start.strftime('%d')}-{date_end.strftime('%d')} {date_end.strftime('%b %Y')}"
            case 'fortnightly':
                return f"{date_start.strftime('%d %b %Y')} -> {date_end.strftime('%d %b %Y')}"
        return f"{date_start.strftime('%d %b %Y')} -> {date_end.strftime('%d %b %Y')}"

    # CSV Line preparation

    def _prepare_general_information(self, line):
        """ Returns a tuple containing the general information required for a line of eMPF contribution. """
        self.ensure_one()
        # This check is not perfect, but it will be improved once we implement casual employees.
        # At that time, we plan to add a separate payroll structure type to make the distinction.
        regular_employee_structure = self.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57')
        is_regular_employee = line.version_id.structure_type_id == regular_employee_structure

        id_number = (line.version_id.identification_id or line.version_id.passport_id).replace('(', '').replace(')', '')

        return (
            line.version_id.l10n_hk_mpf_scheme_id.registration_number,              # Scheme Registration No.
            line.version_id.l10n_hk_mpf_scheme_id.employer_account_number,          # Employer Account No.
            line.version_id.l10n_hk_payroll_group_id.group_id or None,              # Payroll Group ID
            line.version_id.department_id.name or '',                               # Department Code
            self.contribution_period_start.strftime('%Y%m%d'),                      # Payroll Contribution Period Start Date
            self.contribution_period_end.strftime('%Y%m%d'),                        # Payroll Contribution Period End Date
            "",  # Contribution Day (for Casual Employee of Industry Scheme only) - Odoo does not support this feature yet.
            'REE' if is_regular_employee else 'CEE',                                # Employee Account Type
            "HKID" if line.version_id.identification_id else "PASSPORT",            # ID Type
            id_number,                                                              # ID No.
            line.employee_id._get_first_version_date().strftime('%Y%m%d'),          # Date of Employment
            line.status,                                                            # Member's Status
        )

    def _prepare_member_contribution_information(self, line):
        """ Returns a tuple containing the member contribution information required for a line of eMPF contribution. """
        self.ensure_one()

        # Terminated employee without contributions shouldn't report anything here.
        any_contributions = any(
            amount != 0 for amount in (line.ermc, line.eemc, line.ervc, line.ervc_2, line.eevc)
        )

        # In some cases, an employee can have a line (new registration) but no contributions (only start at due date)
        # In that case, we need to skip this section.
        if not line._has_reached_due_date() or (line.status == 'T' and not any_contributions):
            return (None,) * 17  # We still need to have the columns in the file, but empty

        # Skip adding the basic salary if not required (only when used as definition of income for VC)
        eevc = line.version_id.l10n_hk_member_class_ct_eevc_id
        ervc = line.version_id.l10n_hk_member_class_ct_ervc_id
        ervc2 = line.version_id.l10n_hk_member_class_ct_ervc2_id
        basic_salary = None
        if any(vc and vc.definition_of_income == 'basic_salary' for vc in (eevc, ervc, ervc2)):
            basic_salary = line.basic_salary

        # Shouldn't be included if employee is new, pay at due date and due date isn't here
        total = line.total_contributions + line.employer_surcharge + line.employee_surcharge
        # For VC/Surchages must always be empty if 0. EEMC/ERMC must be 0 if no contribution in the period, or empty if any but not that one.
        ermc = line.ermc if line.ermc or not any_contributions else None
        eemc = line.eemc if line.eemc or not any_contributions else None
        return (
            line.mpf_account_number or '',                      # Member Account No.
            line.version_id.l10n_hk_staff_number or '',         # Staff No.
            line.contribution_start_date.strftime('%Y%m%d'),    # Member Contribution Period Start Date
            line.contribution_end_date.strftime('%Y%m%d'),      # Member Contribution Period End Date
            "",  # No. of Working Days (for Casual Employee of Industry Scheme only) - Odoo does not support this feature yet.
            "",  # Working Period Start Date (for Casual Employee of Industry Scheme only) - Odoo does not support this feature yet.
            "",  # Working Period End Date (for Casual Employee of Industry Scheme only) - Odoo does not support this feature yet.
            line.relevant_income,                               # Relevant Income
            basic_salary,                                       # Basic Salary
            ermc,                                               # Employer's Mandatory Contribution
            eemc,                                               # Employee's Mandatory Contribution
            line.ervc or None,                                  # Employer's Voluntary Contribution
            line.ervc_2 or None,                                # Employer's Voluntary Contribution 2
            line.eevc or None,                                  # Employee's Voluntary Contribution
            line.employer_surcharge or None,                    # Employer's Surcharge
            line.employee_surcharge or None,                    # Employee's Surcharge
            total,                                              # Total Amount
        )

    def _prepare_new_member_information(self, line):
        """ Returns a tuple containing the member contribution information required for a line of eMPF contribution. """
        self.ensure_one()
        if line.status != 'N':
            return (None,) * 15  # We still need to have the columns in the file, but empty

        version = line.version_id
        employee = line.employee_id
        if not line.employee_id.l10n_hk_mpf_scheme_join_date:
            # Find the earliest line of status 'N' and get its start date
            employee_lines = self.contribution_line_ids.filtered(lambda line: line.employee_id == employee and line.status == 'N').sorted('contribution_start_date')
            first_new_line = next(iter(employee_lines))
            line.employee_id.l10n_hk_mpf_scheme_join_date = max(first_new_line.contribution_start_date, line.employee_id._get_first_version_date())

        employee_type = "NEW"
        previous_date_of_empl = None
        visa_issue_date = None
        if version.l10n_hk_mpf_exempt:
            employee_type = "EXEMPT"
        elif employee.l10n_hk_previous_employment_date:
            employee_type = "INTRA_GROUP"
            previous_date_of_empl = employee.l10n_hk_previous_employment_date
        elif employee.l10n_hk_visa_issue_date:
            employee_type = "EXPATRIATE"
            visa_issue_date = employee.l10n_hk_visa_issue_date

        # We already checked that this is a valid number, but we still need to parse it again to get the details.
        try:
            phone_nbr = phone_validation.phone_parse(employee.private_phone, employee.country_id.code)
        except UserError:
            phone_nbr = phone_validation.phone_parse(employee.private_phone, employee.company_country_code)

        commencement_date_of_vesting = version._get_commencement_date_for_vesting()
        genders = {
            'male': 'M',
            'female': 'F',
            'other': 'U',
            False: 'O',
        }
        return (
            genders.get(employee.sex, 'O'),                                                         # Gender
            employee.l10n_hk_surname or '',                                                         # Surname (English)
            employee.l10n_hk_given_name or '',                                                      # Given Name (English)
            employee.l10n_hk_name_in_chinese or '',                                                 # Surname (Chinese)
            "",  # Given Name (Chinese) - Unsupported as we have only one field
            version.l10n_hk_mpf_scheme_join_date.strftime('%Y%m%d'),                                # Date of Joining the Scheme
            employee.birthday.strftime('%Y%m%d'),                                                   # Date of Birth
            version.l10n_hk_member_class_id.name or '',                                             # Member Class
            commencement_date_of_vesting and commencement_date_of_vesting.strftime('%Y%m%d'),       # Commencement Date for Vesting Entitlement
            employee_type,                                                                          # Employee Type
            previous_date_of_empl and previous_date_of_empl.strftime('%Y%m%d'),                     # Previous Date of Employment
            visa_issue_date and visa_issue_date.strftime('%Y%m%d'),                                 # Visa Issue date
            employee.private_email,                                                                 # Email Address
            phone_nbr.country_code,                                                                 # Mobile Phone No. (Country Code)
            phone_nbr.national_number,                                                              # Mobile Phone No.
        )

    def _prepare_termination_of_member_information(self, line):
        """ Returns a tuple containing the member contribution information required for a line of eMPF contribution. """
        self.ensure_one()
        if line.status != 'T':
            return (None,) * 3  # We still need to have the columns in the file, but empty

        return (
            line.version_id.departure_date.strftime('%Y%m%d'),              # Last Date of Employment
            line.version_id.departure_reason_id.l10n_hk_empf_code,          # Reason of Termination
            line.termination_payment_type or '',    # Long Service Payment/Severance Payment
        )

    # Report Lines computation

    def _create_contribution_lines(self):
        """
        We expect to see one contribution line for each line that would be in the CSV file.
        Typically, it means one per employees, but in some cases we could see multiple line for a single employee.
        E.g. When we start paying contribution at due date, we need to back-pay for the first or two months of contribution.

        There should neve be more than one line per employee per period, so in practice we will see one line per payslips.
        Lines need to be categorized as some extra information is needed in some cases.

        - If we are registering a new employee, it will be categorized as "new" and we need to provide the employee information.
        - If we are terminating an employee, it will be categorized as "terminated" and we need to provide the termination reason
        and whether we are applying MPF offsetting through SP/LSP.

        When the report is automatically created from a payslip run, only employees present in the run will be taken for the
        report, even if they have the same payroll group ID.

        Note that depending on the configuration, you could see some employee being registered through the file without their
        contributions, which would appear at the payment due date as back-pay.
        """
        self.ensure_one()
        # Never recompute the lines for validated reports.
        if self.state == 'validated':
            return

        # We start by gathering the payslips for the current period/group.
        # These include employees who will be registered, but whose contribution won't be yet.
        payslips = self._gather_period_slips()._l10n_hk_filter_slips_requiring_reporting()

        if not payslips:
            self.contribution_line_ids = [Command.clear()]
            return

        # We look in the employees of the current period to see if any is set to start contributing at due date and reached that date.
        new_contributors = self._gather_new_contributors(payslips)
        # We then look back at these employees past payslips, as we will need to back-pay their contributions.
        payslips |= self._gather_new_contributors_past_payslips(new_contributors)

        # Having gathered all the required payslips, we can now build our contribution lines.
        contribution_line_values = []
        existing_lines_per_payslip = self.contribution_line_ids.grouped('payslip_id')
        for employee, employee_payslips in payslips.sorted(reverse=True).grouped('employee_id').items():
            payslips_per_periods = employee_payslips.grouped('date_from')
            for i, (_date_from, period_payslips) in enumerate(payslips_per_periods.items()):
                period_payslip = period_payslips.filtered(lambda p: p.struct_id.code == 'CAP57MONTHLY')
                # Special case where we do not contribute in a period, and only register termination through a SP/LSP
                if not period_payslip:
                    period_payslip = period_payslips.filtered(lambda p: p.struct_id.code in ['CAP57SEVERANCE', 'CAP57LONG'])
                if not period_payslip:  # Unexpected
                    continue
                payslip = next(iter(period_payslip))

                status = 'E'
                mpf_reg_status = payslip.version_id.l10n_hk_mpf_registration_status
                departure_date = payslip.version_id.departure_date
                # An employee is considered new (and thus to be registered) if their status is "Register At Next Contribution"
                # We need to set the status on the first line, as the system need to register the employee before the contributions.
                if mpf_reg_status == 'next_contribution':
                    status = 'N'
                elif i == len(payslips_per_periods) - 1 and departure_date and departure_date <= self.contribution_period_end and mpf_reg_status == 'registered':
                    status = 'T'

                # Special case: employee for whom we pay at due date (which didn't arrive yet) but we already registered;
                # We will skip these completely and back pay later.
                due_date = payslip.employee_id._get_first_version_date() + relativedelta(days=59)
                at_due_date = payslip.version_id.l10n_hk_mpf_contribution_start == "at_due_date"
                reached_due_date = due_date.replace(day=1) <= self.contribution_period_end.replace(day=1)
                if status != 'N' and at_due_date and not reached_due_date:
                    continue

                line_data = {
                    'payslip_id': payslip.id,
                    'status': status,
                }

                # As there is quite a bit of computation in the lines, instead of trying to edit them we will recreate
                # but ensure to keep the manually set data that are not computed.
                if existing_line := existing_lines_per_payslip.get(payslip):
                    line_data.update({
                        'employee_surcharge': existing_line.employee_surcharge,
                        'employer_surcharge': existing_line.employer_surcharge,
                    })

                contribution_line_values.append(Command.create(line_data))
        self.contribution_line_ids = [Command.clear()] + contribution_line_values

    def _gather_period_slips(self):
        """
        Gather and return the payslips relevant to this report.

        While it is required to separate employees of different scheme in separate CSV, there is no rules about separating
        by group.
        That said, this is useful to support as different Payroll Officers could be in charge of different groups of
        employees.

        When a payslip run is linked to the report, the payslips will be picked from it instead.
        """
        self.ensure_one()
        if self.payslip_run_id:
            return self.payslip_run_id.slip_ids.filtered(lambda s: s.version_id.l10n_hk_mpf_scheme_id == self.scheme_id)

        domain = (
            Domain("state", "in", ["validated", "paid"])
            & Domain("company_id", "=", self.company_id.id)
            & Domain("date_from", ">=", self.contribution_period_start)
            & Domain("date_to", "<=", self.contribution_period_end)
            & Domain("version_id.l10n_hk_mpf_scheme_id", "=", self.scheme_id.id)
            & Domain("version_id.l10n_hk_mpf_registration_status", "in", ["next_contribution", "registered"])
            # We avoid picking payslips from other reports, but self is ok as we call this when recomputing the lines.
            & Domain("l10n_hk_contribution_line_id", "=", False)
            | Domain("l10n_hk_contribution_line_id.report_id", "in", self.ids)
        )
        if self.payroll_group_id:
            domain &= Domain("version_id.l10n_hk_payroll_group_id", "=", self.payroll_group_id.id)

        return self.env['hr.payslip'].search(domain)

    def _gather_new_contributors(self, current_period_payslips):
        """
        Employees who are set to "start contributions" at due date and reached said due date need to be picked up at this
        stage, so that we can find their past payslips and handle back-payments of employer (and voluntary) contributions.
        """
        self.ensure_one()
        first_time_contributor_ids = set()
        for payslip in current_period_payslips:
            version = payslip.version_id
            if version.l10n_hk_mpf_contribution_start == 'at_due_date':
                # Figure out when the first payment date is due.
                # It is on the month following their 60th day of employment, and as we report the past month when compare this
                # date with the payslip
                sixtieth_day = version.employee_id._get_first_version_date() + relativedelta(days=59)
                if sixtieth_day.replace(day=1) == self.contribution_period_end.replace(day=1):  # same month
                    first_time_contributor_ids.add(version.id)
            elif version.l10n_hk_mpf_contribution_start == 'immediate' and version.l10n_hk_mpf_registration_status == 'next_contribution':
                # The other case of first contribution is employee that are being registered, and start contributing right away.
                # We will also back-pay for these if necessary
                first_time_contributor_ids.add(version.id)

        return self.env['hr.version'].browse(first_time_contributor_ids)

    def _gather_new_contributors_past_payslips(self, new_contributors):
        """
        Gather pas payslips of new contributors.
        This only pick payslips that are for the current contract/version.
        """
        self.ensure_one()
        new_contributors_payslip_ids = set()
        for contributor in new_contributors:
            all_contribution_payslips = self.env['hr.payslip'].search([
                ('state', 'in', ['paid', 'validated']),
                ('date_to', '>=', contributor.employee_id._get_first_version_date()),
                ('date_to', '<=', self.contribution_period_end),
                ('version_id', '=', contributor.id),
            ])
            new_contributors_payslip_ids.update(all_contribution_payslips.ids)
        return self.env['hr.payslip'].browse(new_contributors_payslip_ids)

    def _prepare_error_check_dict(self):
        """
        This method will return a dictionary that can be used by the report to validate the data of the lines, and by the
        line to find the error message related to errors raised during the validation.

        The lambda checks are run by passing to it a specific report line.

        :returns a dict of the format: {
            'error_code' : {
                'check': lambda check,
                'message': translated error message,
            }
        }
        """
        # This one is more complex as we rely on phone_parse and need to catch the exceptions, so it is defined differently.
        def _phone_check(line):
            if not line.employee_id.private_phone:
                return False  # There is a separate check for that

            try:
                phone_validation.phone_parse(line.employee_id.private_phone, line.employee_id.country_id.code)
            except UserError:
                try:
                    phone_validation.phone_parse(line.employee_id.private_phone, line.employee_id.company_country_code)
                except UserError:
                    return True
            return False

        return {
            'missing_status': {
                'check': lambda line: not line.status,
                'message': self.env._("You must have a Status set on every lines oif the report."),
            },
            'department_name_limit': {
                'check': lambda line: line.version_id.department_id and len(line.version_id.department_id.name) > 50,
                'message': self.env._("Department names cannot be longer than 50 characters."),
            },
            'missing_reason_of_departure': {
                'check': lambda line: line.status == 'T' and not line.version_id.departure_reason_id.l10n_hk_empf_code,
                'message': self.env._("You must set a Reason Of Termination (eMPF) for all departure types used by the eMPF system."),
            },
            # Note that we don't check the years of services, these would be handled in the payslip.
            'wrong_lsp': {
                'check': lambda line: line.status == 'T' and line.termination_payment_type == 'L' and line.version_id.departure_reason_id.l10n_hk_empf_code not in ['DEATH', 'DISMIS', 'CONTRACT_END', 'ILL_HEALTH', 'RETIRE'],
                'message': self.env._("Long service payments are only allowed for terminations due to Death, Dismissal, End of contract, Ill health or Retirement."),
            },
            'wrong_sp': {
                'check': lambda line: line.status == 'T' and line.termination_payment_type == 'S' and line.version_id.departure_reason_id.l10n_hk_empf_code not in ['REDUNDANCY', 'LAID_OFF'],
                'message': self.env._("Severance payments are only allowed for terminations due to Redundancy or Lay off."),
            },
            'missing_phone_number': {
                'check': lambda line: line.status == 'N' and not line.employee_id.private_phone,
                'message': self.env._("You must set a Private Phone for all new employees being registered to the eMPF system."),
            },
            'incorrect_phone_number': {
                'check': _phone_check,
                'message': self.env._("The Private Phone number must be from the country of the employee, or the country of the company."),
            },
            'missing_birthday': {
                'check': lambda line: line.status == 'N' and not line.employee_id.birthday,
                'message': self.env._("You must set a Birthday for all new employees being registered to the eMPF system."),
            },
            'missing_email': {
                'check': lambda line: line.status == 'N' and not line.employee_id.private_email,
                'message': self.env._("You must set a Private Email for all new employees being registered to the eMPF system."),
            },
            'missing_id': {
                'check': lambda line: not line.version_id.identification_id and not line.version_id.passport_id,
                'message': self.env._("You must set a Identification No or Passport No for all employees using the eMPF system."),
            },
            'missing_name': {
                'check': lambda line: not (line.employee_id.l10n_hk_surname and line.employee_id.l10n_hk_given_name) and not line.employee_id.l10n_hk_name_in_chinese,
                'message': self.env._("You must either set the Surname and Given Name or the Name in Chinese for all employees using the eMPF system."),
            },
            'too_young_to_work': {
                'check': lambda line: line.employee_id.birthday and line.employee_id.birthday > fields.Date.context_today(self) - relativedelta(years=16),
                'message': self.env._("Employees reported to the eMPF cannot be younger than 16 years old."),
            },
            'numbered_employee': {
                'check': lambda line: re.match(r'.*\d.*', f"{line.employee_id.l10n_hk_surname} {line.employee_id.l10n_hk_given_name} {line.employee_id.l10n_hk_name_in_chinese}"),
                'message': self.env._("Employees reported to the eMPF cannot have numbers in their name."),
            },
        }
