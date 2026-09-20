# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Knowledge Website',
    'summary': 'Publish your articles',
    'version': '1.0',
    'depends': ['knowledge', 'website'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/knowledge_views.xml',
        'views/knowledge_templates_public.xml',
    ],
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'website_knowledge/static/src/backend/**/*',
        ],
        'web.assets_frontend': [
            'knowledge/static/src/scss/knowledge_variables.scss',
            'knowledge/static/src/portal_webclient/router_utils.js',
            'knowledge/static/src/components/article_search_dialog/article_search_dialog.*',
            'knowledge/static/src/editor/embedded_components/core/**/*',
            'knowledge/static/src/editor/html_migrations/**/*',
            'website_knowledge/static/src/frontend/**/*',
        ],
        'web.assets_tests': [
            'website_knowledge/static/tests/tours/**/*',
        ],
        'web._assets_primary_variables': [
            'website_knowledge/static/src/scss/primary_variables.scss',
        ],
        'website_knowledge.assets_public_knowledge': [
            ('include', 'web.assets_frontend'),
            ('before', 'website_knowledge/static/src/scss/primary_variables.scss', 'website_knowledge/static/src/scss/website_knowledge.scss'),
        ],
        'website_knowledge.assets_knowledge_print': [
            'website_knowledge/static/src/frontend/knowledge_public_view/knowledge_public_view_print.scss',
        ],
        'web.assets_unit_tests': [
            'website_knowledge/static/tests/**/*',
            ('remove', 'website_knowledge/static/tests/tours/**/*'),
        ],
        'website.website_builder_assets': [
            'website_knowledge/static/src/plugins/**/*',
        ],
    },
}
