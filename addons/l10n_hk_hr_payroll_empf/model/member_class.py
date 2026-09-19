# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import RedirectWarning, ValidationError


class l10n_hkMemberClass(models.Model):
    _name = 'l10n_hk.member.class'
    _description = "Hong Kong: Member Class"
    _order = 'is_default DESC, name, id'

    # ------------------
    # Fields declaration
    # ------------------

    name = fields.Char(
        required=True,
        translate=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
        required=True,
    )
    scheme_id = fields.Many2one(
        comodel_name='l10n_hk.mpf.scheme',
        string="Scheme",
        required=True,
        ondelete='cascade',
    )
    definition_of_service = fields.Selection(
        string="Definition of Service For Vesting",
        selection=[
            ('date_of_employment', "From the Date of Employment"),
            ('date_of_joining_scheme', "From the Date of Joining Scheme"),
            ('previous_date_of_employment', "From the Previous Date of Employment"),
        ],
        default='date_of_employment',
        required=True,
    )
    is_default = fields.Boolean()
    contribution_type_ids = fields.One2many(
        comodel_name='l10n_hk.member.class.contribution.type',
        inverse_name='member_class_id',
    )
    employee_ids = fields.One2many(
        comodel_name='hr.employee',
        inverse_name='l10n_hk_member_class_id',
    )

    # ----------------------------
    # Onchange, Constraint methods
    # ----------------------------

    _default_uniq = models.UniqueIndex(
        '(is_default, company_id, scheme_id) WHERE is_default IS TRUE',
        "You cannot have more than one default Member Class for a given scheme.",
    )

    @api.constrains('name')
    def _contraints_format(self):
        for member_class in self:
            if len(member_class.name) > 50:
                raise ValidationError(
                    self.env._("The Member Class name must be a maximum of 50 characters.")
                )

    # -----------------------
    # CRUD, inherited methods
    # -----------------------

    @api.ondelete(at_uninstall=False)
    def _unlink_if_no_employee(self):
        """
        This check is there to avoid unintended side effects when deleting a group.
        If removing it from the employees is intentional, it should be done manually there first.
        """
        if self.employee_ids:
            raise RedirectWarning(
                message=self.env._("You cannot delete a Member Class that has employees assigned to it."),
                action=self.employee_ids._get_records_action(),
                button_text=self.env._('List Employees') if len(self.employee_ids) > 1 else self.env._('Show Employee'),
            )

    # --------------
    # Action methods
    # --------------

    def action_open_employee_list(self):
        self.ensure_one()
        return self.employee_ids._get_records_action(name=self.env._("Employees"))
