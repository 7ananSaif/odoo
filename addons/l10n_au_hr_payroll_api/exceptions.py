# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _
from odoo.exceptions import UserError


def _l10n_au_raise_user_error(message: str):
    """Create a UserError for Australian Payroll with a specific message."""
    raise UserError(_("Australian Payroll Error: %s", message))
