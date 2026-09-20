{  # noqa: B018
    "name": "Phone - SMS",
    "version": "1.0",
    "category": "Sales/Sales",
    "depends": ["voip", "sms"],
    "auto_install": True,
    "license": "OEEL-1",
    "assets": {
        "web.assets_backend": [
            "voip_sms/static/src/**/*",
        ],
    },
    "author": "Odoo S.A.",
}
