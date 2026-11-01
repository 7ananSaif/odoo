{
    "name": "Admin Developer Mode",
    "version": "19.0.1.1.0",
    "summary": "Developer mode for system administrators + Settings page tweaks",
    "description": """
Developer-mode behaviour for system administrators:

* Forces developer mode on for every member of ``base.group_system`` by
  overriding ``ir.http.session_info()``.
* Hides the "Developer Tools" block from General Settings: with the mode
  forced on, that block is both pointless and a way for administrators to
  turn the technical tooling off by accident.
* Points the copyright link of the "About" block at the deployment URL
  (``BASE_URL``) instead of ``https://www.odoo.com``.

SECURITY: developer mode is active for administrators on every request,
including in production. Uninstall the module to revert.
""",
    "author": "Hanan",
    "license": "LGPL-3",
    "category": "Administration",
    "depends": ["web", "base_setup"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "admin_dev_mode/static/src/xml/settings_branding.xml",
            "admin_dev_mode/static/src/js/settings_branding.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
