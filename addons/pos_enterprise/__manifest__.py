# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Point of Sale enterprise',
    'category': 'Sales/Point of Sale',
    'summary': 'Advanced features for PoS',
    'description': """
Advanced features for the PoS like better views 
for IoT Box config.   
""",
    'data': [
        'security/ir.model.access.csv',
        'security/preparation_display_security.xml',
        'views/res_config_settings_views.xml',
        'views/preparation_display_assets_index.xml',
        'views/preparation_display_view.xml',
        'wizard/preparation_display_reset_wizard.xml',
        'data/preparation_display_cron.xml',
        'views/pos_order_view.xml',
        'views/pos_preparation_time_report_view.xml',
    ],
    'depends': ['web_enterprise', 'point_of_sale'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_enterprise/static/src/override/point_of_sale/**/*',
            ('remove', 'pos_enterprise/static/src/override/point_of_sale/**/*.dark.scss'),
        ],
        'point_of_sale.assets_prod_dark': [
            ('include', 'web.dark_mode_variables'),
            # web._assets_backend_helpers
            ('before', 'web_enterprise/static/src/scss/bootstrap_overridden.scss', 'web_enterprise/static/src/scss/bootstrap_overridden.dark.scss'),
            ('after', 'web/static/lib/bootstrap/scss/_functions.scss', 'web_enterprise/static/src/scss/bs_functions_overridden.dark.scss'),
            # assets_backend
            'web_enterprise/static/src/**/*.dark.scss',
            'pos_enterprise/static/src/**/*.dark.scss',
        ],
        'pos_preparation_display.assets': [
            # 'preparation_display' bootstrap customization layer
            'web/static/src/scss/functions.scss',
            'pos_enterprise/static/src/scss/primary_variables.scss',
            ("include", "point_of_sale.base_app"),
            'web/static/src/webclient/webclient.scss',
            'web/static/src/webclient/icons.scss',
            'point_of_sale/static/src/utils.js',
            "point_of_sale/static/src/app/utils/devices_identifier_sequence.js",

            'mail/static/src/core/common/sound_effects_service.js',
            'point_of_sale/static/src/overrides/sound_effects_service.js',
            'pos_enterprise/static/src/app/**/*',

            # Related models from point_of_sale
            'point_of_sale/static/src/proxy_trap.js',
            'point_of_sale/static/src/lazy_getter.js',
            "point_of_sale/static/src/app/models/data_service_options.js",
            "point_of_sale/static/src/app/models/utils/indexed_db.js",
            "point_of_sale/static/src/app/utils/pretty_console_log.js",
            "point_of_sale/static/src/app/models/related_models/**/*",
            "point_of_sale/static/src/app/services/data_service.js",
            "point_of_sale/static/src/app/models/pos_preset.js",
            "point_of_sale/static/src/app/models/pos_category.js",
        ],
        'pos_preparation_display.assets_tour_tests': [
            ("include", "point_of_sale.base_tests"),
            "pos_enterprise/static/tests/tours/preparation_display/**/*"
        ],
        'web.assets_tests': [
            'pos_enterprise/static/tests/tours/point_of_sale/**/*',
        ],
        'web.assets_backend': [
            'pos_enterprise/static/src/backend/components/fields/duration_field.js',
            'pos_enterprise/static/src/backend/components/fields/duration_field.xml',
        ],
        'web.assets_unit_tests_setup': [
            ('include', 'pos_preparation_display.assets'),
            ('remove', 'pos_enterprise/static/src/app/root.js'),

            # Remove CSS files since we're not testing the UI with hoot in PoS preparation display
            # CSS files make html_editor tests fail
            ('remove', 'pos_enterprise/static/src/**/*.scss'),

            # Re-include debug and router files that were removed in point_of_sale.base_app
            # but are required for running unit tests
            'web/static/src/core/debug/**/*',
            'web/static/src/core/browser/router.js',
        ],
        'web.assets_unit_tests': [
            'pos_enterprise/static/tests/unit/**/*',
        ],
    },
}
