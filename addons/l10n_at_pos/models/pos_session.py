from odoo import models, _
from odoo.exceptions import ValidationError


class PosSession(models.Model):
    _inherit = 'pos.session'

    def write(self, vals):
        if self.company_id.l10n_at_fiskaly_api_secret and self.currency_id.is_zero(vals.get("cash_register_balance_start", 0)):
            if not self.company_id.l10n_at_fiskaly_access_token or not self.company_id.l10n_at_is_fon_authenticated:
                raise ValidationError(_("Please authenticate Fiskaly credentials & FON before starting any session."))
            if self.company_id.currency_id.rounding != 0.01:
                raise ValidationError(_("The currency rounding should be 0.01 to start a session with Fiskaly."))
        return super().write(vals)
