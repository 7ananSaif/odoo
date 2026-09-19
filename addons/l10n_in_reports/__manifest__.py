{
    'name': 'Indian - Accounting Reports',
    'version': '1.1',
    'description': """
Accounting reports for India
================================
    """,
    'category': 'Accounting/Localizations/Reporting',
    'depends': [
        'l10n_in',
        'account_reports',
        'accountant',
        'account_batch_payment',
        'barcodes',
        'account_invoice_extract',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/service_cron.xml',
        'data/mail_activity_type_data.xml',
        'data/account_tax_report_tds_tcs_data.xml',
        'data/account_financial_html_report_gstr1.xml',
        'data/account_financial_html_report_gstr2b.xml',
        'data/account_financial_html_report_gstr3b.xml',
        'data/profit_and_loss.xml',
        'data/bank_template.xml',
        'data/enet_payment_methods.xml',
        'data/account_return_data.xml',
        'wizard/gst_otp_validation.xml',
        'views/gstr_document_summary_views.xml',
        'wizard/gstr1_submission_wizard.xml',
        'views/account_return_views.xml',
        'views/account_return_check_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings.xml',
        'views/account_journal_dashboard_view.xml',
        'views/account_batch_payment_views.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],
    'installable': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'l10n_in_reports/static/src/**/*',
        ],
    },
    'external_dependencies': {
        'python': ['pyjwt'],
        'apt': {
            'pyjwt': 'python3-jwt',
        },
    },
}
