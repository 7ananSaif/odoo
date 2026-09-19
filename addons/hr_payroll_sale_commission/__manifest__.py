# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Commission in Payslips',
    'version': '1.0',
    'category': 'Human Resources/Payroll',
    'sequence': 95,
    'summary': 'Autofill employee commission',
    'description': """
Payment of employee commission
=====================================

This application allows you to pay commission in payslips.
    """,
    'depends': ['sale_commission', 'hr_payroll'],
    'data': [
        'views/sale_commission_plan.xml',
    ],
    'auto_install': True,
    'installable': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
