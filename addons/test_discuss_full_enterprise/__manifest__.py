# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Test Discuss Full Enterprise',
    'category': 'Hidden',
    'summary': 'Test Suite for Discuss Enterprise',
    'auto_install': ['test_discuss_full', 'web_enterprise'],
    'depends': [
        'ai',
        'account_accountant',
        'account_invoice_extract',
        'approvals',
        'documents',
        'knowledge',
        'mail_enterprise',
        'sign',
        'test_discuss_full',
        'voip',
        'voip_ai',
        'voip_onsip',
        'web_enterprise',
        'website_helpdesk_livechat',
        'web_studio',
        'whatsapp',
    ],
    'assets': {
        'web.assets_tests': [
            'test_discuss_full_enterprise/static/tests/tours/**/*',
        ],
        'web.assets_unit_tests': [
            'test_discuss_full_enterprise/static/tests/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
