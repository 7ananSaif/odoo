# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard


def _post_init_auth_l10n_au_hr_payroll(env):
    """ Security setup for Australian Payroll Integration:
        - Require authentication after  maximum 30 mins of inactivity
        - Set session lock timeout to 24 hours.
        - Enable MFA for session lock timeout.
    """
    groups = env["res.groups"]._l10n_au_get_privileged_groups()
    for group in groups:
        # Session timeout
        vals = {"lock_timeout_mfa": True}  # Enable MFA for session lock timeout
        if not group.lock_timeout or group.lock_timeout > 24 * 60:
            vals["lock_timeout"] = 24 * 60  # 24 hours

        # Inactivity timeout
        if not group.lock_timeout_inactivity or group.lock_timeout_inactivity > 30:
            vals["lock_timeout_inactivity"] = 30
        # MFA not required for inactivity lock timeout
        group.write(vals)
