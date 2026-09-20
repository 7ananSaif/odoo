from odoo import models, api, _
from odoo.exceptions import ValidationError


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.ondelete(at_uninstall=False)
    def _l10n_au_unlink_attachments(self):
        attachments = self.env.ref("l10n_au_hr_payroll_api.l10n_au_payroll_odoo_disclaimer") | self.env.ref("l10n_au_hr_payroll_api.l10n_au_payroll_superchoice_dda")
        if self.filtered(lambda r: r in attachments):
            raise ValidationError(
                _("You cannot delete attachments related to Australian Payroll. Please contact your administrator.")
            )
