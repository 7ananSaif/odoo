{
    'name': 'MuK Backend Theme',
    'summary': 'Odoo Community Backend Theme',
    'description': """
        This module offers a mobile compatible design for Odoo Community.
        Furthermore it allows the user to define some design preferences.
    """,
    'version': '19.0.1.4.5',
    'category': 'Themes/Backend',
    'license': 'LGPL-3',
    'author': 'MuK IT',
    'website': 'http://www.mukit.at',
    'live_test_url': 'https://my.mukit.at/r/f6m',
    'contributors': [
        'Mathias Markl <mathias.markl@mukit.at>',
    ],
    'depends': [
        'muk_web_group',
        'muk_web_chatter',
        'muk_web_dialog',
        'muk_web_appsbar',
        'muk_web_colors',
        'muk_web_refresh',
    ],
    # MuK Backend Theme only supports the Community backend, so it must not be
    # installed alongside web_enterprise. Do NOT comment this out: the entry
    # itself never broke anything, the failure came from 'auto_install' below.
    'excludes': [
        'web_enterprise',
    ],
    'data': [
        'templates/web_layout.xml',
        'views/res_config_settings.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            (
                'after',
                'web/static/src/scss/primary_variables.scss',
                'muk_web_theme/static/src/scss/colors.scss',
            ),
            (
                'after',
                'web/static/src/scss/primary_variables.scss',
                'muk_web_theme/static/src/scss/variables.scss',
            ),
        ],
        'web.assets_backend': [
            'muk_web_theme/static/src/webclient/**/*.xml',
            'muk_web_theme/static/src/webclient/**/*.scss',
            'muk_web_theme/static/src/webclient/**/*.js',
            'muk_web_theme/static/src/views/**/*.scss',
        ],
        'web.assets_unit_tests': [
            'muk_web_theme/static/tests/**/*.test.js',
        ],
    },
    'images': [
        'static/description/banner.png',
        'static/description/theme_screenshot.png',
    ],
    'installable': True,
    'application': False,
    # Auto-install is intentionally enabled: the backend theme is the base
    # module for the rest of the MuK Web suite, so it is selected on every
    # database whose dependencies it can satisfy (all of its dependencies are
    # community auto-install modules: muk_web_group / appsbar / colors /
    # chatter / dialog / refresh).
    #
    # WARNING: because 'excludes' above lists web_enterprise, a database that
    # also installs web_enterprise will abort during install with:
    #
    #   UserError: Modules "MuK Backend Theme" and "Web Enterprise" are
    #              incompatible.
    #
    # This affects enterprise-only databases (CI, the Hotel industry package).
    # Remove the 'excludes' entry if the theme must coexist with web_enterprise.
    'auto_install': True,
    'post_init_hook': '_setup_module',
    'uninstall_hook': '_uninstall_cleanup',
}
