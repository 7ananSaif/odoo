# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import werkzeug

from odoo import http, tools, _
from odoo.http import request


class KnowledgeController(http.Controller):

    # ------------------------
    # Article Access Routes
    # ------------------------

    @http.route('/knowledge/home', type='http', auth='user')
    def access_knowledge_home(self):
        """ This route will redirect internal users to the backend view of the
        article and the share users to the frontend view instead. """
        article = request.env["knowledge.article"]._get_first_accessible_article()
        if request.env.user._is_internal():
            return self._redirect_to_backend_view(article)
        return self._redirect_to_portal_view(article)

    @http.route('/knowledge/article/<int:article_id>', type='http', auth='user')
    def redirect_to_article(self, article_id, show_resolved_threads=False):
        """ This route will redirect internal users to the backend view of the
        article and the share users to the frontend view instead."""
        article = request.env['knowledge.article'].with_context(active_test=False).search([('id', '=', article_id)])
        if not article:
            return werkzeug.exceptions.Forbidden()

        if request.env.user._is_internal():
            return self._redirect_to_backend_view(article, show_resolved_threads)
        return self._redirect_to_portal_view(article)

    @http.route('/knowledge/article/invite/<int:member_id>/<string:invitation_hash>', type='http', auth='public')
    def article_invite(self, member_id, invitation_hash):
        """ This route will check if the given parameter allows the client to access the article via the invite token.
        Then, if the partner has not registered yet, we will redirect the client to the signup page to finally redirect
        them to the article.
        If the partner already has registrered, we redirect them directly to the article.
        """
        member = request.env['knowledge.article.member'].sudo().browse(member_id).exists()
        correct_token = member._get_invitation_hash() if member else False
        if not correct_token or not tools.consteq(correct_token, invitation_hash):
            raise werkzeug.exceptions.NotFound()

        partner = member.partner_id
        article = member.article_id

        if not partner.user_ids:
            # Force the signup even if not enabled (as we explicitly invited the member).
            # They should still be able to create a user.
            signup_allowed = request.env['res.users']._get_signup_invitation_scope() == 'b2c'
            if not signup_allowed:
                partner.signup_prepare()
            partner.signup_get_auth_param()
            signup_url = partner._get_signup_url_for_action(url='/knowledge/article/%s' % article.id)[partner.id]
            return request.redirect(signup_url)

        return request.redirect('/web/login?redirect=/knowledge/article/%s' % article.id)

    def _redirect_to_backend_view(self, article, show_resolved_threads=False):
        if article.id and show_resolved_threads:
            action_id = request.env.ref('knowledge.knowledge_article_action_form_show_resolved').id
            return request.redirect(f'/odoo/action-{action_id}/{article.id}')
        return request.redirect(f'/odoo/knowledge/{article.id or "new"}')

    def _redirect_to_portal_view(self, article):
        # We build the session information necessary for the web client to load
        session_info = request.env['ir.http'].session_info()

        session_info.update(
            user_companies={
                'current_company': request.env.company.id,
                'allowed_companies': {
                    request.env.company.id: {
                        'id': request.env.company.id,
                        'name': request.env.company.name,
                    },
                },
            },
        )

        return request.render(
            'knowledge.knowledge_portal_view',
            {'session_info': session_info},
        )
