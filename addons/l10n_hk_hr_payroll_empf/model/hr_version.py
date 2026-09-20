# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError


class HrVersion(models.Model):
    _inherit = 'hr.version'

    # ------------------
    # Fields declaration
    # ------------------

    l10n_hk_mpf_exempt = fields.Boolean(
        string="Exempt of MPF",
        help="Enable this to disable mandatory contributions. Voluntary contributions can still be used regardless of this setting.",
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
    )
    l10n_hk_mpf_registration_status = fields.Selection(
        string="Registration Status",
        help="When set to 'Next Contribution', the employee registration will be handled automatically through the next eMPF Contributions Report.",
        selection=[
            ('next_contribution', "Register At Next Contribution"),
            ('registered', "Registered"),
            ('terminated', "Terminated"),
        ],
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
    )
    l10n_hk_mpf_contribution_start = fields.Selection(
        string="Start Contribution",
        help="Set this to 'Immediately' to start registering contributions through the eMPF Contributions Report as soon as the employee is registered for MPF. "
             "If Set to 'At Due Date', the contributions will only start after the 60 days period, and back-payments records will be added to the report if needed.",
        selection=[
            ('immediate', "Immediately Upon Registration"),
            ('at_due_date', "At Due Date"),
        ],
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
    )
    l10n_hk_mpf_scheme_id = fields.Many2one(
        comodel_name='l10n_hk.mpf.scheme',
        string="MPF Scheme",
        groups='hr_payroll.group_hr_payroll_user',
        domain="[('employer_account_number', '!=', False)]",
        tracking=True,
    )
    l10n_hk_payroll_group_id = fields.Many2one(
        comodel_name='l10n_hk.payroll.group',
        string="Payroll Group",
        help="Precising the group is optional, but becomes mandatory if the company uses more than one group for the employee scheme.",
        groups='hr_payroll.group_hr_payroll_user',
        domain="[('company_id', '=', company_id), ('scheme_id', '=', l10n_hk_mpf_scheme_id)]",
        compute='_compute_l10n_hk_payroll_group',
        store=True,
        tracking=True,
    )
    l10n_hk_member_class_id = fields.Many2one(
        comodel_name='l10n_hk.member.class',
        string="Member Class",
        groups='hr_payroll.group_hr_payroll_user',
        domain="[('company_id', '=', company_id), ('scheme_id', '=', l10n_hk_mpf_scheme_id)]",
        compute='_compute_l10n_hk_member_class',
        store=True,
        tracking=True,
    )
    l10n_hk_mpf_account_number = fields.Char(
        string="Member Account No.",
        help="Precising the account is optional, but becomes mandatory if the employee uses more than one active member account under the same employer and payroll group.",
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
    )
    l10n_hk_mpf_scheme_join_date = fields.Date(
        string="Date of Joining the Scheme",
        help="Leave empty to set the date automatically upon registering through the eMPF Contributions Report.",
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
    )
    # This is optional, but we may as well support it.
    l10n_hk_staff_number = fields.Char(
        string="Staff No.",
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
    )
    # Technical fields
    l10n_hk_scheme_group_count = fields.Integer(
        compute="_compute_l10n_hk_scheme_group_count",
        groups='hr_payroll.group_hr_payroll_user',
        export_string_translation=False,
    )
    l10n_hk_member_class_ct_eevc_id = fields.Many2one(
        comodel_name='l10n_hk.member.class.contribution.type',
        groups='hr_payroll.group_hr_payroll_user',
        compute='_compute_employee_member_class_contribution_types',
        export_string_translation=False,
    )
    l10n_hk_member_class_ct_ervc_id = fields.Many2one(
        comodel_name='l10n_hk.member.class.contribution.type',
        groups='hr_payroll.group_hr_payroll_user',
        compute='_compute_employee_member_class_contribution_types',
        export_string_translation=False,
    )
    l10n_hk_member_class_ct_ervc2_id = fields.Many2one(
        comodel_name='l10n_hk.member.class.contribution.type',
        groups='hr_payroll.group_hr_payroll_user',
        compute='_compute_employee_member_class_contribution_types',
        export_string_translation=False,
    )

    # --------------------------------
    # Compute, inverse, search methods
    # --------------------------------

    @api.depends('l10n_hk_mpf_scheme_id')
    def _compute_l10n_hk_payroll_group(self):
        """
        Set the default group on an employee when a scheme is selected.
        We do not overwrite the group if it is set to another one from the same scheme.
        If the scheme is changed to another one with no defaults, we empty the group.
        """
        default_groups = self.env['l10n_hk.payroll.group']._read_group(
            domain=[('is_default', '=', True)],
            groupby=['company_id', 'scheme_id'],  # Schemes are shared between companies, but the groups are specific to a company.
            aggregates=['id:recordset'],
        )
        default_groups_dict = {(company, scheme): default_group for company, scheme, default_group in default_groups}
        for employee in self:
            default_group = default_groups_dict.get((employee.company_id, employee.l10n_hk_mpf_scheme_id))
            group_is_of_employee_scheme = employee.l10n_hk_payroll_group_id.scheme_id == employee.l10n_hk_mpf_scheme_id
            if default_group and not group_is_of_employee_scheme:
                employee.l10n_hk_payroll_group_id = default_group
            elif employee.l10n_hk_payroll_group_id and not group_is_of_employee_scheme:
                employee.l10n_hk_payroll_group_id = False

    @api.depends('l10n_hk_mpf_scheme_id')
    def _compute_l10n_hk_member_class(self):
        """
        Set the default member class on an employee when a scheme is selected.
        We do not overwrite the class if it is set to another one from the same scheme.
        If the scheme is changed to another one with no defaults, we empty the class.
        """
        default_classes = self.env['l10n_hk.member.class']._read_group(
            domain=[('is_default', '=', True)],
            groupby=['company_id', 'scheme_id'],
            aggregates=['id:recordset'],
        )
        default_classes_dict = {(company, scheme): default_class for company, scheme, default_class in default_classes}
        for employee in self:
            default_class = default_classes_dict.get((employee.company_id, employee.l10n_hk_mpf_scheme_id))
            class_is_of_employee_scheme = employee.l10n_hk_member_class_id.scheme_id == employee.l10n_hk_mpf_scheme_id
            if default_class and not class_is_of_employee_scheme:
                employee.l10n_hk_member_class_id = default_class
            elif employee.l10n_hk_member_class_id and not class_is_of_employee_scheme:
                employee.l10n_hk_member_class_id = False

    @api.depends('l10n_hk_mpf_scheme_id')
    def _compute_l10n_hk_scheme_group_count(self):
        """
        The payroll group is optional information if the company only has one.
        As soon as a company has more than one group for a scheme, this information becomes required.
        """
        for employee in self:
            if not employee.l10n_hk_mpf_scheme_id:
                employee.l10n_hk_scheme_group_count = 0
            else:
                employee.l10n_hk_scheme_group_count = len(employee.l10n_hk_mpf_scheme_id.payroll_group_ids)

    def _compute_employee_member_class_contribution_types(self):
        """ These shortcuts makes it easier to set up salary rules and such without the need to parse the contribution types each time.  """
        for employee in self:
            contribution_type_ids = employee.l10n_hk_member_class_id.contribution_type_ids.grouped('contribution_type')
            employee.write({
                'l10n_hk_member_class_ct_eevc_id': contribution_type_ids.get('employee', False),
                'l10n_hk_member_class_ct_ervc_id': contribution_type_ids.get('employer', False),
                'l10n_hk_member_class_ct_ervc2_id': contribution_type_ids.get('employer_2', False),
            })

    # ----------------------------
    # Onchange, Constraint methods
    # ----------------------------

    @api.constrains('l10n_hk_staff_number')
    def _contraints_staff_number(self):
        """ Enforce the format required by the eMPF system. """
        for version in self:
            if version.l10n_hk_staff_number and not re.match(r'^[a-zA-Z0-9]{,20}$', version.l10n_hk_staff_number):
                raise ValidationError(
                    self.env._("The Staff Number must be a maximum of 20 characters and can only contain letters (a-Z) and numbers (0-9). "
                               "Please do not use spaces or symbols.")
                )

    # ----------------
    # Business methods
    # ----------------

    def _get_commencement_date_for_vesting(self):
        """ Returns the commencement date based on the option set on the member class of the employee. """
        self.ensure_one()
        if not self.l10n_hk_member_class_id:
            return None

        date_field_name = start_date = None
        match self.l10n_hk_member_class_id.definition_of_service:
            case 'date_of_employment':
                start_date = self.employee_id._get_first_version_date()
            case 'date_of_joining_scheme':
                start_date = self.l10n_hk_mpf_scheme_join_date
            case 'previous_date_of_employment':
                start_date = self.l10n_hk_previous_employment_date

        # Fallback to the _get_first_version_date if the definition_of_service doesn't match the expected values; but it shouldn't happen.
        start_date = start_date or self.employee_id._get_first_version_date()
        if not start_date:
            start_date_string = self._fields[date_field_name].get_description(self.env)["string"]
            raise UserError(
                self.env._(
                    "You must set the %(start_date_string)s for employee %(employee_name)s in order to properly calculate the vested percentage.",
                    start_date_string=start_date_string,
                    employee_name=self.name,
                )
            )
        return start_date
