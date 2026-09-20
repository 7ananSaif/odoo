# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _name = "res.users"
    _inherit = ["l10n_au.audit.logging.mixin", "res.users"]
    # Force the mixin to be at the bottom to pass context to prevent
    # duplications due to group_ids

    @api.model
    def _get_display_name_fields(self):
        return ["name"]

    @api.model
    def _get_audit_logging_fields(self):
        return ["password", "company_ids"]

    def _records_to_log(self):
        return self.filtered(lambda r: "AU" in r.mapped("company_ids.country_code"))

    def _is_privileged_australian_user(self):
        """Check if the user is a privileged user for Australian Payroll."""
        self.ensure_one()
        sudo_self = self.sudo()
        if "AU" not in sudo_self.company_ids.mapped("country_code"):
            return False
        return self in sudo_self.env["res.groups"]._l10n_au_get_privileged_groups().user_ids

    def _mfa_type(self):
        """ Enforce TOTP MFA for privileged Australian users. """
        r = super()._mfa_type()
        if r is not None:
            return r
        if self._is_privileged_australian_user():
            return 'totp_mail'

    def _restrict_social_oauth(self):
        """ Prevent the use of social media accounts for OAuth for Australian users. """
        facebook_auth = self.env.ref("auth_oauth.provider_facebook", raise_if_not_found=False)
        for user in self:
            if user._is_internal() and facebook_auth:
                if user["oauth_provider_id"] == facebook_auth:
                    raise ValidationError(
                        _("The Facebook OAuth provider is not supported for internal users with the Australian Payroll Integration!")
                    )

    def write(self, vals):
        if "oauth_provider_id" in vals:
            self._restrict_social_oauth()
        return super().write(vals)

    def create(self, vals):
        users = super().create(vals)
        if "oauth_provider_id" in self._fields:
            users._restrict_social_oauth()
        return users
