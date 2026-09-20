# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Point of Sale Appointment',
    'version': '1.0',
    'category': 'Sales/Point of Sale',
    'sequence': 6,
    'summary': 'This module lets you manage online reservations for PoS',
    'website': 'https://www.odoo.com/app/appointments',
    'depends': ['appointment', 'point_of_sale'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/calendar_event_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        # Having the editor add a lot of files to the PoS bundle.
        # We can maybe find a way to have a "light editor" with smaller bundle
        'pos_appointment.html_editor': [
            ('include', 'html_editor.assets_editor'),
            'html_editor/static/src/others/dynamic_placeholder_plugin.js',
            'html_editor/static/src/main/placeholder_plugin.js',
            'html_editor/static/src/backend/**/*',
            ("remove", "html_editor/static/src/utils/regex.js"),
            'html_editor/static/src/fields/html_field*',

            'web/static/lib/dompurify/DOMpurify.js',
        ],
        'point_of_sale._assets_pos': [
            ('include', 'pos_appointment.html_editor'),
            'web_gantt/static/src/**/*',
            'pos_appointment/static/src/**/*',
            'appointment/static/src/components/appointment_booking_action_helper/*',
            'appointment/static/src/components/appointment_type_sync_duration/*',
            'appointment/static/src/views/gantt/**/*',
            'appointment/static/src/xml/appointment_svg.xml',
            'calendar/static/src/scss/calendar_event_views.scss',
            'calendar/static/src/views/**/*',
            ('remove', 'web_gantt/static/src/**/*.dark.scss'),
        ],
        'point_of_sale.assets_prod_dark': [
            'web_gantt/static/src/**/*.dark.scss',
        ],
        'web.assets_unit_tests_setup': [
            # Adding error handler back since they are removed in the prod bundle
            'html_editor/static/src/utils/regex.js',
            'web_gantt/static/src/**/*.dark.scss'
        ],
        'web.assets_unit_tests': [
            'pos_appointment/static/tests/unit/**/*'
        ],
    }
}
