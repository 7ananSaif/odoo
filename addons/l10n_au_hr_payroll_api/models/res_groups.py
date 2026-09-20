# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _
from odoo.exceptions import ValidationError


class ResGroups(models.Model):
    _name = "res.groups"
    _inherit = ["res.groups", "l10n_au.audit.logging.mixin"]

    def _l10n_au_get_privileged_groups(self):
        """ Returns a list of privileged groups for security checks and logging.
            This includes all the accounting, payroll, and system groups.
        """
        privileges = (
            # Accounting
            self.env.ref("account.res_groups_privilege_accounting")
            + self.env.ref("account.res_group_privilege_accounting_bank")
            # Payroll
            + self.env.ref("hr.res_groups_privilege_employees")
            + self.env.ref("hr_payroll.res_groups_privilege_payroll")
            + self.env.ref("hr_holidays.res_groups_privilege_time_off")
            + (
                self.env.ref("hr_expense.res_groups_privilege_expenses", raise_if_not_found=False)
                or self.env["res.groups.privilege"].browse()
            )  # If hr_expense installed
        )

        return self.env["res.groups"].search([("privilege_id", "in", privileges.ids)]) + self.env.ref("base.group_system")

    def _records_to_log(self):
        groups = self._l10n_au_get_privileged_groups()
        return self.filtered(lambda r: r in groups)

    @api.constrains("lock_timeout", "lock_timeout_mfa", "lock_timeout_inactivity")
    def _check_lock_timeout(self):
        """ Ensure the lock timeout and inactivity settings are valid.
            - Mandatory MFA for previleged groups.
            - 24 hours session lock timeout.
            - MFA required for session lock timeout.
            - lock_timeout_inactivity <= 30 min
        """
        session_timeout_limit = 24 * 60  # 24 hours
        inactivity_timeout_limit = 30  # 30 minutes
        privileged_groups = self._l10n_au_get_privileged_groups()
        for group in self.filtered(lambda g: g in privileged_groups):
            if group.lock_timeout and group.lock_timeout > session_timeout_limit:
                raise ValidationError(_("The lock timeout for Australian Payroll privileged groups cannot exceed 24 hours!"))
            if not group.lock_timeout_mfa:
                raise ValidationError(_("Privileged groups must require MFA for session lock timeout!"))
            if group.lock_timeout_inactivity > inactivity_timeout_limit:
                raise ValidationError(_("The inactivity lock timeout for Australian Payroll privileged groups cannot exceed 30 minutes!"))
