{
    'name': 'Stock - WhatsApp',
    'summary': 'Send whatsapp messages when final stock move',
    'description': 'Send WhatsApp messages when a stock transfer is validated',
    'category': 'WhatsApp',
    'version': '1.0',
    'depends': ['stock_enterprise', 'whatsapp'],
    'data': [
        'data/whatsapp_template_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'auto_install': True,
    'uninstall_hook': '_reset_whatsapp_text_confirmation',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
