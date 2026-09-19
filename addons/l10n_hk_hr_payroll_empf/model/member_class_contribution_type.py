# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class l10n_hkMemberClassContributionType(models.Model):
    _name = 'l10n_hk.member.class.contribution.type'
    _description = "Hong Kong: Member Class Contribution Type"
    _order = 'contribution_type, id'

    # ------------------
    # Fields declaration
    # ------------------

    member_class_id = fields.Many2one(
        comodel_name='l10n_hk.member.class',
        string="Member Class",
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        related='member_class_id.company_id',
        required=True,
        store=True,
        precompute=True,  # Required stored field, so we need it pre-computed
    )
    contribution_type = fields.Selection(
        selection=[
            ('employee', "Employee's Voluntary Contribution"),
            ('employer', "Employer's Voluntary Contribution"),
            ('employer_2', "Employer's Voluntary Contribution 2"),
        ],
        required=True,
    )
    contribution_option = fields.Selection(
        string="Option",
        selection=[
            ('percentage', "Fixed Percentage of Income"),
            ('fixed', "Fixed Amount"),
            ('match', "Match Employee's Voluntary Contribution"),
            ('top_up', "Fixed Percentage of Income minus Mandatory Contribution"),
        ],
        required=True,
    )
    amount = fields.Float(
        help="Amount of the contribution, depends of the ",
        compute='_compute_amount',
        readonly=False,
        store=True,
        recursive=True,
        required=True,
        precompute=True,
    )
    definition_of_income = fields.Selection(
        selection=[
            ('basic_salary', "Basic Salary"),
            ('relevant_wages', "Relevant Wages"),
        ],
        compute='_compute_definition_of_income',
        readonly=False,
        store=True,
        recursive=True,
        precompute=True,
    )

    # ----------------------------
    # Onchange, Constraint methods
    # ----------------------------

    _contribtype_uniq = models.UniqueIndex(
        '(company_id, member_class_id, contribution_type)',
        "You cannot have more than one Contribution Type of each type in a same Member Class.",
    )

    # --------------------------------
    # Compute, inverse, search methods
    # --------------------------------

    @api.depends('contribution_option', 'member_class_id.contribution_type_ids')
    def _compute_amount(self):
        """
        When the contribution option of an employer's contribution is set to "Match Employee's Voluntary Contribution",
        we compute the amount to match the employee's one.
        This avoids the need to compute this later on when we need to process the contributions.
        """
        contribution_type_ids = self._read_group(
            domain=[('contribution_type', '=', 'employee')],
            groupby=['company_id', 'member_class_id'],
            aggregates=['id:recordset'],
        )
        contribution_types_dict = {(company.id, member_class.id): contribution_type for company, member_class, contribution_type in contribution_type_ids}
        for contribution in self:
            company_id = contribution._origin.company_id or contribution.company_id
            member_class_id = contribution._origin.member_class_id or contribution.member_class_id
            employee_contribution_type = contribution_types_dict.get((company_id._origin.id, member_class_id._origin.id))
            if contribution.contribution_option == 'match' and employee_contribution_type:
                contribution.amount = employee_contribution_type.amount

    @api.depends('contribution_option', 'member_class_id.contribution_type_ids')
    def _compute_definition_of_income(self):
        """
        When the contribution option of an employer's contribution is set to "Match Employee's Voluntary Contribution",
        we compute the definition to match the employee's one.
        This avoids the need to compute this later on when we need to process the contributions.
        """
        contribution_type_ids = self._read_group(
            domain=[('contribution_type', '=', 'employee')],
            groupby=['company_id', 'member_class_id'],
            aggregates=['id:recordset'],
        )
        contribution_types_dict = {(company.id, member_class.id): contribution_type for company, member_class, contribution_type in contribution_type_ids}
        for contribution in self:
            company_id = contribution._origin.company_id or contribution.company_id
            member_class_id = contribution._origin.member_class_id or contribution.member_class_id
            employee_contribution_type = contribution_types_dict.get((company_id._origin.id, member_class_id._origin.id))
            if contribution.contribution_option == 'match' and employee_contribution_type:
                contribution.definition_of_income = employee_contribution_type.definition_of_income

    # ----------------------------
    # Onchange, Constraint methods
    # ----------------------------

    @api.constrains('contribution_type', 'contribution_option')
    def _contraints_employee_contribution_cannot_be_match(self):
        result = self._search(domain=[('contribution_type', '=', 'employee'), ('contribution_option', '=', 'match')])
        if result:
            raise ValidationError(
                self.env._("Employee Voluntary Contribution cannot use the option 'Match Employee`s Voluntary Contribution'.")
            )
