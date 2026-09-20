# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class l10n_hkMpfScheme(models.Model):
    _name = 'l10n_hk.mpf.scheme'
    _description = "Hong Kong: MPF Scheme"
    _order = 'employer_account_number, registration_number'

    # ------------------
    # Fields declaration
    # ------------------

    name = fields.Char(
        string="MPF Scheme",
        required=True,
        translate=True,
    )
    registration_number = fields.Char(
        string="Registration Number",
        required=True,
    )
    employer_account_number = fields.Char(
        string="Employer Account No.",
        company_dependent=True,
        help="This value is specific to the currently selected company.",
    )
    payroll_group_ids = fields.One2many(
        comodel_name='l10n_hk.payroll.group',
        string="Payroll Groups",
        domain=lambda self: [('company_id', '=', self.env.company.id)],
        inverse_name='scheme_id',
    )
    member_class_ids = fields.One2many(
        comodel_name='l10n_hk.member.class',
        string="Member Classes",
        domain=lambda self: [('company_id', '=', self.env.company.id)],
        inverse_name='scheme_id',
    )

    # --------------------------------
    # Compute, inverse, search methods
    # --------------------------------

    @api.depends('name', 'employer_account_number')
    @api.depends_context('company')
    def _compute_display_name(self):
        """ Appends the company-specific employer account number to the name of the scheme. """
        for scheme in self:
            if scheme.employer_account_number:
                scheme.display_name = f'{scheme.name} ({scheme.employer_account_number})'
            else:
                scheme.display_name = scheme.name

    @api.constrains('registration_number')
    def _contraints_single_default(self):
        result = self._read_group(
            domain=[],
            groupby=['registration_number'],
            aggregates=['id:recordset'],
            having=[('__count', '>', 1)],
        )
        if result:
            raise ValidationError(
                self.env._("You cannot have multiple MPF Scheme with a same Registration Number.")
            )
