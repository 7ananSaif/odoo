# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Test Sign',
    'version': '1.0',
    'category': 'Sales/Sign',
    'summary': "Sign Test case",
    'description': """
Sign and complete your documents easily. Customize your documents with text and signature fields and send them to your recipients.\n
Let your customers follow the signature process easily.
    """,
    'depends': [
        'sign',
        'sale',
        'crm',
        'mrp',
        'hr_expense',
    ],
    'installable': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
