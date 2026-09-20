# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Stripe compatible API version is '2025-01-27.acacia'
{
    'name': 'Expense cards',
    'version': '1.0',
    'category': 'Human Resources/Expenses',
    'sequence': 70,
    'summary': 'Create and manage company expense cards via Stripe',
    'author': 'Odoo S.A.',
    'description': """Stripe Issuing integration for expenses""",
    'website': 'https://www.odoo.com/app/expenses',
    'depends': ['hr_expense', 'certificate'],
    'data': [

        'data/config_parameter.xml',
        'data/product.mcc.stripe.tag.csv',
        'data/ir_cron.xml',
        'data/mail_template_data.xml',
        'data/mail_activity_type_data.xml',
        'data/mail_message_subtype.xml',

        'views/hr_expense_stripe_card_views.xml',
        'views/hr_expense_views.xml',
        'views/account_journal_views.xml',
        'views/account_journal_dashboard_views.xml',
        'views/product_mcc_stripe_tag_views.xml',
        'views/product_product_views.xml',
        'views/res_config_settings.xml',

        'wizard/hr_expense_stripe_cardholder_wizard.xml',
        'wizard/hr_expense_stripe_card_receive_wizard.xml',
        'wizard/hr_expense_stripe_card_block_wizard.xml',
        'wizard/hr_expense_stripe_topup_wizard.xml',

        'security/ir.model.access.csv',
        'security/hr_expense_stripe_card_security.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_expense_stripe/static/src/components/*',
            'hr_expense_stripe/static/src/fields/*',
            'hr_expense_stripe/static/src/css/stripe_card.scss',
        ],
        'web.assets_web_dark': [
            'hr_expense_stripe/static/src/css/*dark.scss',
        ],
    },
    'post_init_hook': '_post_init_hook_setup_issuing',
    'uninstall_hook': '_uninstall_hook',
    'installable': True,
    'license': 'LGPL-3',
}
