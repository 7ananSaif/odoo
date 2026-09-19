{  # noqa: B018
    "name": "Phone - CRM",
    "summary": "Phone integration with CRM module.",
    "description": "Adds a button to schedule calls from kanban leads.",
    "category": "Sales/CRM",
    "version": "1.0",
    "depends": ["crm", "voip"],
    "auto_install": True,
    "data": [
        "views/crm_lead_views.xml",
        "views/voip_call_views.xml",
        "security/voip_crm_security.xml",
    ],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "assets": {
        "web.assets_backend": [
            "voip_crm/static/src/**/*",
        ],
        "web.assets_unit_tests": [
            "voip_crm/static/tests/**/*",
        ],
    },
}
