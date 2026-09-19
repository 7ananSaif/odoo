{  # noqa: B018
    "name": "Phone",
    "summary": """Make and receive phone calls from within Odoo.""",
    "description": """Adds a softphone and helpers to make phone calls directly from within your Odoo database.""",
    "category": "Productivity/Phone",
    "sequence": 280,
    "version": "2.0",
    "depends": ["base", "mail", "phone_validation", "web", "web_mobile"],
    "data": [
        "security/voip_security.xml",
        "data/voip_data.xml",
        "security/ir.model.access.csv",
        "views/voip_provider_views.xml",   # load before res_config_settings_views.xml
        "views/voip_call_views.xml",
        "views/res_users_views.xml",
        "views/res_users_settings_views.xml",
        "views/res_config_settings_views.xml",
        "views/voip_menu_views.xml",
    ],
    "demo": [
        "demo/res_groups.xml",
    ],
    "application": True,
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "assets": {
        "voip.assets_sip": [
            "voip/static/lib/sip.js"
        ],
        "web.assets_backend": [
            "voip/static/src/**/*",
            ("remove", "voip/static/src/**/*.dark.scss"),
        ],
        "voip.assets_public": [
            'mail/static/src/core/common/**/*',
        ],
        "web.assets_web_dark": [
            "voip/static/src/**/*.dark.scss",
        ],
        "web.assets_unit_tests": [
            "voip/static/tests/**/*",
        ],
    },
}
