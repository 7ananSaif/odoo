from odoo.http import request, route
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.utils import is_user_internal


class KnowledgeHome(Home):

    @route()
    def web_client(self, s_action=None, **kw):
        ''' Redirects non-internal users attempting to access the Knowledge
            backend view to the Knowledge public or portal view'''
        if kw.get('subpath') is not None and (not request.session.uid or not is_user_internal(request.session.uid)):
            if (url_parts := kw.get('subpath').split('/')) and len(url_parts) >= 2:
                *_, action_id, article_id = url_parts
                action_form = 'knowledge.knowledge_article_action_form'
                form_resolved = 'knowledge.knowledge_article_action_form_show_resolved'
                if (
                    action_id == 'knowledge'
                    or action_id == f'action-{request.env.ref(action_form).id}'
                    or action_id == f'action-{request.env.ref(form_resolved).id}'
                ):
                    return request.redirect(f'/knowledge/article/{article_id}')
        return super().web_client(s_action=s_action, **kw)
