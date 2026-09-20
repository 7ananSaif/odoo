# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'France - Payroll with Accounting',
    'category': 'Human Resources',
    'countries': ['fr'],
    'depends': ['l10n_fr_hr_payroll', 'hr_payroll_account', 'l10n_fr_account'],
    'data': [
        'data/hr_salary_rule_data.xml',
    ],
    'description': """
Accounting Data for French Payroll Rules.

This module is based on an unsupported France module. Please consider that we won't support this module.
--------------------------------------------------------------------------------------------------------
    """,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
