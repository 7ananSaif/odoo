{  # noqa: B018
    "name": "Phone - Subscriptions",
    "summary": "Phone integration with Subscriptions module.",
    "category": "Sales/Subscriptions",
    "version": "1.0",
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "depends": ["voip", "sale_subscription"],
    "auto_install": True,
    "data": ["views/voip_call_views.xml"],
}
