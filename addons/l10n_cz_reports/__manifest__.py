# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Czech Republic- Accounting Reports',
    'icon': '/account/static/description/l10n.png',
    'version': '1.0',
    'description': """
Accounting reports for Czech Republic
=====================================
This module includes accounting reports for Czech Republic, including:
- VAT Control Statement (creation and XML export). For more information, see https://adisspr.mfcr.cz/dpr/adis/idpr_pub/epo2_info/popis_struktury_detail.faces?zkratka=DPHKH1
- Souhrnné hlášení VIES Report (creation and XML export). For more information, see https://adisspr.mfcr.cz/dpr/adis/idpr_pub/epo2_info/popis_struktury_detail.faces?zkratka=DPHSHV
- Tax report (XML export). For more information, see https://adisspr.mfcr.cz/dpr/adis/idpr_pub/epo2_info/popis_struktury_detail.faces?zkratka=DPHDP3
    """,
    'category': 'Accounting/Localizations/Reporting',
    'depends': ['l10n_cz', 'account_reports'],
    'data': [
        'data/account_return_data.xml',
        'data/profit_loss.xml',
        'data/balance_sheet.xml',
        'data/account_report_ec_sales_list_report.xml',
        'data/tax_report.xml',
        'data/common_report_export.xml',
        'data/control_statement_report_export.xml',
        'data/control_statement_report.xml',
        'data/tax_report_export.xml',
        'data/vies_summary_report_export.xml',
        'data/vies_summary_report.xml',
        'views/account_move_views.xml',
        'views/account_tax_views.xml',
        'views/product_template_views.xml',
    ],
    'post_init_hook': '_l10n_cz_reports_post_init',
    'auto_install': True,
    'installable': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
