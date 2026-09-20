# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import http
from odoo.http import request
from odoo.addons.knowledge.controllers.main import KnowledgeController
from werkzeug.exceptions import NotFound


class KnowledgeWebsiteController(KnowledgeController):

    # ------------------------
    # Article Access Routes
    # ------------------------

    @http.route('/knowledge/home', type='http', auth='public', website=True, sitemap=False)
    def access_knowledge_home(self):
        if request.env.user._is_public():
            article = request.env["knowledge.article"]._get_first_accessible_article()
            if not article:
                raise NotFound()
            return request.redirect("/knowledge/article/%s" % article.id)
        return super().access_knowledge_home()

    # Override routes to display articles to public users
    @http.route('/knowledge/article/<int:article_id>', type='http', auth='public', website=True, sitemap=False, multilang=False)
    def redirect_to_article(self, **kwargs):
        if request.env.user._is_public():
            article = request.env['knowledge.article'].sudo().browse(kwargs['article_id'])
            if not article.exists():
                raise NotFound()
            if article.website_published:
                return self._redirect_to_public_view(article, kwargs.get('no_sidebar', False))
            # public users can't access articles that are not published, let them login first
            return request.redirect('/web/login?redirect=/knowledge/article/%s' % kwargs['article_id'])
        return super().redirect_to_article(**kwargs)

    def _redirect_to_public_view(self, article, no_sidebar=False):
        # The sidebar is hidden if no_sidebar is True or if there is no article
        # to show in the sidebar (i.e. only one article in the tree is published).
        return request.render('website_knowledge.article_view_public', {
            'article': article,
            'main_object': article,
            'show_sidebar': bool(
                not no_sidebar
                and (
                    article.parent_id.website_published
                    or article.child_ids.filtered('website_published')
                )
            ),
        })

    # ---------------------------------
    # Published articles data Routes
    # ---------------------------------

    @http.route('/knowledge/public/children', type="jsonrpc", auth='public')
    def get_public_article_children(self, article_id):
        return request.env['knowledge.article'].search_read(
            [('parent_id', '=', article_id), ('is_article_item', '=', False)],
            ['icon', 'name'],
            order='sequence',
        )

    @http.route('/knowledge/public/article', type="jsonrpc", auth='public')
    def get_public_article_content(self, article_id):
        article = self.env['knowledge.article'].browse(article_id)
        if not article or not article.website_published:
            raise NotFound()
        article_data = self._prepare_public_article(article)
        return {
            'content': request.env['ir.qweb']._render('website_knowledge.article_public_content', {
                'article': article_data,
                'show_sidebar': True,
            })
        }

    @http.route('/knowledge/public/sidebar', type='jsonrpc', auth='public')
    def get_public_sidebar_articles(self, article_id):
        accessible_ancestors_ids = self.env['knowledge.article'].browse(article_id)._get_accessible_root_ancestors().ids
        return request.env['knowledge.article'].search_read(
            [
                ('is_article_item', '=', False),
                '|',
                    ('id', 'in', accessible_ancestors_ids),
                    ('parent_id', 'in', accessible_ancestors_ids), ('parent_id', '!=', article_id)
            ],
            ['icon', 'name', 'parent_id'],
            order='parent_id desc, sequence',
            load=False,
        )

    @http.route('/knowledge/public/search', type="jsonrpc", auth='public')
    def search_public_article(self, subsite_root_id, search_value):
        sorted_articles = request.env['knowledge.article'].get_sorted_articles(
            search_value,
            [('website_published', '=', True), ('id', 'child_of', subsite_root_id)]
        )
        for article in sorted_articles:
            del article['is_user_favorite']
            del article['root_article_id']
        return sorted_articles

    def _prepare_public_article(self, article):
        public_fields = {'body', 'cover_image_position', 'cover_image_url', 'display_name',
            'full_width', 'icon'}
        public_article = {field: article[field] for field in public_fields}
        public_article['cover_image_id'] = article.cover_image_id.id
        public_article['id'] = article.id
        return public_article
