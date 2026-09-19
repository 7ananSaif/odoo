# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import RedirectWarning, ValidationError


class l10n_hkPayrollGroup(models.Model):
    _name = 'l10n_hk.payroll.group'
    _description = "Hong Kong: Payroll Group"
    _order = "is_default DESC, name, id"

    # ------------------
    # Fields declaration
    # ------------------

    name = fields.Char(
        required=True,
        translate=True,
    )
    group_id = fields.Char(
        string="Payroll Group ID",
        required=True,
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
    contribution_frequency = fields.Selection(
        selection=[
            ('monthly', "Monthly"),
            ('quarterly', "Quarterly"),
            ('biweekly', "Bi-weekly"),
            ('weekly', "Weekly"),
            ('semi-monthly', "Semi-Monthly"),
            ('fortnightly', "Fortnightly"),
        ],
        default='monthly',
        required=True,
    )
    is_default = fields.Boolean(
        string="Default",
        help="If marked as default, this group will be set on new employees using this scheme."
    )
    employee_ids = fields.One2many(
        comodel_name='hr.employee',
        inverse_name='l10n_hk_payroll_group_id',
    )

    # ----------------------------
    # Onchange, Constraint methods
    # ----------------------------

    _default_uniq = models.UniqueIndex(
        '(is_default, company_id, scheme_id) WHERE is_default IS TRUE',
        "You cannot have more than one default Payroll Group for a given scheme.",
    )

    _groupid_uniq = models.UniqueIndex(
        '(company_id, scheme_id, group_id)',
        "Each Payroll Group of a same scheme must have unique Group ID.",
    )

    @api.constrains('group_id')
    def _contraints_format(self):
        for group in self:
            if len(group.group_id) > 20:
                raise ValidationError(
                    self.env._("The Group ID must be a maximum of 20 characters.")
                )

    @api.ondelete(at_uninstall=False)
    def _unlink_if_no_employee(self):
        """ This check is there to avoid unintended side effects when deleting a group.
        If removing it from the employees is intentional, it should be done manually there first.
        """
        if self.employee_ids:
            raise RedirectWarning(
                message=self.env._("You cannot delete a Payroll Group that has employees assigned to it."),
                action=self.employee_ids._get_records_action(name=self.env._("Employees In Group")),
                button_text=self.env._("List Employees") if len(self.employee_ids) > 1 else self.env._("Show Employee"),
            )

    # --------------
    # Action methods
    # --------------

    def action_open_employee_list(self):
        self.ensure_one()
        return self.employee_ids._get_records_action(name=self.env._("Employees"))
