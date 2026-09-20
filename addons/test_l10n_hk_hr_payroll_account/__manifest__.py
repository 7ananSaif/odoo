# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Test Hong Kong Payroll',
    'countries': ['hk'],
    'category': 'Human Resources',
    'summary': 'Test Hong Kong Payroll',
    'depends': [
        'l10n_hk_hr_payroll_account',
        'documents_l10n_hk_hr_payroll',
        'l10n_hk_hr_payroll_empf',
    ],
    'author': 'Odoo S.A.',
    'post_init_hook': '_generate_payslips',
    'license': 'OEEL-1',
}
