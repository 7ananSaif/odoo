{  # noqa: B018
    "name": "Phone - Helpdesk",
    "summary": "Phone integration with Helpdesk module.",
    "category": "Helpdesk",
    "version": "1.0",
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "depends": ["voip", "helpdesk"],
    "auto_install": True,
    "data": ["views/voip_call_views.xml"],
}
