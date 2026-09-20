
from contextlib import contextmanager
from unittest.mock import patch

try:
    from odoo.addons.l10n_au_hr_payroll_api.models.l10n_au_stp import L10n_AuSTP
    from odoo.addons.l10n_au_hr_payroll_api.models.hr_payslip import Payslip
    from odoo.addons.l10n_au_hr_payroll_api.models.l10n_au_audit_logging_mixin import L10n_AuAuditLoggingMixin
    from odoo.addons.l10n_au_hr_payroll_api.models.l10n_au_superstream import L10n_auSuperStream
    is_stp_api_installed = True
except ImportError:
    is_stp_api_installed = False


@contextmanager
def mock_skip_stp_api_calls():
    """ Context manager to skip all outgoing STP API calls. """
    if is_stp_api_installed:
        with (
            patch.object(L10n_AuSTP, 'submit', lambda self: super(L10n_AuSTP, self).submit()),
            patch.object(Payslip, 'action_payslip_done', lambda self: super(Payslip, self).action_payslip_done()),
            patch.object(L10n_AuAuditLoggingMixin, '_create_audit_logs', lambda self, from_vals={}, create=False: []),
            patch.object(L10n_auSuperStream, '_create_super_stream_file', lambda self: super(L10n_auSuperStream, self)._create_super_stream_file()),
            patch.object(L10n_auSuperStream, 'action_register_super_payment', lambda self: super(L10n_auSuperStream, self).action_register_super_payment()),
        ):
            yield
    else:
        yield
