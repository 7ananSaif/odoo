# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Australia - Payroll with API',
    'category': 'Human Resources',
    'version': '1.0',
    'depends': [
        'l10n_au_hr_payroll_account',
        'account_edi_proxy_client',
        'auth_timeout',
    ],
    'description': """
Single Touch Payroll and Super Stream through Superchoice API
================================================================
This module provides the necessary APIs to handle Single Touch Payroll
(STP) and Super Stream compliances in Australia using the Superchoice API.

This modules uses Superchoice as the Clearing House to manage Superannuation
payments and their api is used to submit STP reports.

It also implements the necessary security and logging features to meet the ATO's
requirements for payroll data handling.
-   Mandatory MFA for Payroll and Accounting users.
-   Maximum of 30 mins Inactivity timeout for privileged users.
-   24-hour session timeout for privileged users.
-   Audit logging for sensitive fields.
    """,
    'auto_install': ['l10n_au_hr_payroll_account'],
    'data': [
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/ir_cron_data.xml",
        "data/ir_config_parameter_data.xml",
        "data/ir_attachments_data.xml",
        "wizard/l10n_au_payroll_register_views.xml",
        "wizard/l10n_au_superstream_cancel_views.xml",
        "views/res_company_views.xml",
        "views/res_config_settings_views.xml",
        "views/l10n_au_stp_views.xml",
        "views/l10n_au_super_fund_views.xml",
        "views/l10n_au_super_stream_views.xml",
        "views/l10n_au_employer_registration_views.xml",
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_post_init_auth_l10n_au_hr_payroll',
}
