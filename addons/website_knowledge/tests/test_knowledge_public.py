# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml import html

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests.common import HttpCase, JsonRpcException, tagged, users


@tagged('post_install', '-at_install', 'knowledge_public', 'knowledge_tour')
class TestKnowledgePublic(HttpCase):
    @classmethod
    def setUpClass(cls):
        super(TestKnowledgePublic, cls).setUpClass()
        cls.public_user = mail_new_test_user(
            cls.env,
            email='my_public@public.com',
            groups='base.group_public',
            name='Public User',
            login='custom_public_user',
        )
        # remove existing articles to ease tour management
        cls.env['knowledge.article'].with_context(active_test=False).search([]).unlink()
        cls.attachment = cls.env['ir.attachment'].create({
            'name': 'pixel',
            'datas': 'R0lGODlhAQABAIAAAP///wAAACwAAAAAAQABAAACAkQBADs=',
            'res_model': 'knowledge.cover',
            'res_id': 0
        })
        cls.cover = cls.env['knowledge.cover'].create({
            'attachment_id': cls.attachment.id
        })

        # create test articles
        # - Unpublished Root
        #     - Published Root      (should appear as the root for a public user)
        #         - Published Child
        #             - Published Subchild
        #             - Untitled             --> <p>Some content</p>
        #         - Unpublished Child        --> <p>Some unpublished content</p>
        #         - Published Item
        # - Other Root
        #     - Other Child                  --> <p>Some other content</p>
        cls.unpublished_root = cls.env['knowledge.article'].create([{'name': "Unpublished Root"}])
        cls.root_article = cls.env['knowledge.article'].create([{'name': "Published Root", 'website_published': True, 'cover_image_id': cls.cover.id, 'parent_id': cls.unpublished_root.id, 'icon': '🐣'}])
        cls.root_children = cls.env['knowledge.article'].create([
            {'name': "Published Child", 'website_published': True, 'parent_id': cls.root_article.id},
            {'name': "Unpublished Child", "website_published": False, 'parent_id': cls.root_article.id, 'body': "<p>Some unpublished content</p>"},
            {'name': "Published Item", "website_published": True, 'parent_id': cls.root_article.id, 'is_article_item': True},
        ])
        cls.subchildren = cls.env['knowledge.article'].create([
            {"name": "Published Subchild", 'website_published': True, 'parent_id': cls.root_children[0].id},
            {"name": False, 'website_published': True, 'parent_id': cls.root_children[0].id, 'body': "<p>Some content</p>"},
        ])

        cls.other_root = cls.env['knowledge.article'].create([{'name': "Other Root", 'website_published': True}])
        cls.env['knowledge.article'].create([
            {'name': "Other Child", 'website_published': True, 'parent_id': cls.other_root.id, 'body': "<p>Some other content</p>"},
        ])

    def test_knowledge_meta_tags(self):
        """ Check that the meta tags set on the article's frontend page showcase the article content.
            The description meta tag should be a small extract from the article and should exclude
            special blocs such as the table of content, the files, the embedded views, the videos, etc."""

        article = self.env['knowledge.article'].create({
            'icon': '💬',
            'name': 'Odoo Experience',
            'body': '''
                <h1>What is Odoo Experience?</h1>
                <div data-embedded="tableOfContent">Hello</div>
                <p>Odoo Experience is our largest event, taking place once a year.</p>
                <p>It brings together all members of the Odoo sphere, including partners, customers and open source software fans.</p>
            ''',
            'cover_image_id': self.cover.id,
            'website_published': True,
        })

        # Check that the special blocs are excluded from the summary
        self.assertEqual(
            article.summary,
            'What is Odoo Experience? Odoo Experience is our largest event, taking place once a year. It brings t...')

        res = self.url_open(f'/knowledge/article/{article.id}')
        root_html = html.fromstring(res.content)

        # Check the meta tag of the article frontend page:

        # Standard meta tags:
        self.assertEqual(
            root_html.xpath('/html/head/meta[@name="description"]/@content'),
            ['What is Odoo Experience? Odoo Experience is our largest event, taking place once a year. It brings t...'])

        # OpenGraph meta tags:
        self.assertEqual(
            root_html.xpath('/html/head/meta[@property="og:type"]/@content'),
            ['article'])
        self.assertEqual(
            root_html.xpath('/html/head/meta[@property="og:title"]/@content'),
            ['💬 Odoo Experience'])
        self.assertEqual(
            root_html.xpath('/html/head/meta[@property="og:description"]/@content'),
            ['What is Odoo Experience? Odoo Experience is our largest event, taking place once a year. It brings t...'])
        self.assertEqual(
            root_html.xpath('/html/head/meta[@property="og:image"]/@content'),
            [article.get_base_url() + article.cover_image_url])

        # X meta tags:
        self.assertEqual(
            root_html.xpath('/html/head/meta[@name="twitter:title"]/@content'),
            ['💬 Odoo Experience'])
        self.assertEqual(
            root_html.xpath('/html/head/meta[@name="twitter:description"]/@content'),
            ['What is Odoo Experience? Odoo Experience is our largest event, taking place once a year. It brings t...'])
        self.assertEqual(
            root_html.xpath('/html/head/meta[@name="twitter:card"]/@content'),
            ['summary_large_image'])
        self.assertEqual(
            root_html.xpath('/html/head/meta[@name="twitter:image"]/@content'),
            [article.get_base_url() + article.cover_image_url])

    @users('custom_public_user')
    def test_knowledge_public_article_routes(self):
        # article route for a published article should return correct data
        request_result = self.make_jsonrpc_request("/knowledge/public/article", {'article_id': self.root_article.id})
        rendered_article = html.fromstring(request_result['content'])
        self.assertTrue(rendered_article.xpath("//div[contains(@class, 'o_knowledge_article_display_name')]//span[text()='🐣 Published Root']"))
        self.assertTrue(rendered_article.xpath("//div[contains(@class, 'o_readonly')]//h1[text()='Published Root']"))

        # article route for non published article should raise an access error
        with self.assertRaises(JsonRpcException, msg='odoo.exceptions.AccessError'):
            self.make_jsonrpc_request("/knowledge/public/article", {'article_id': self.unpublished_root.id})

        # sidebar for root of subsite should only contain root
        self.assertEqual(self.make_jsonrpc_request("/knowledge/public/sidebar", {'article_id': self.root_article.id}), [
            {'id': self.root_article.id, 'icon': '🐣', 'name': 'Published Root', 'parent_id': self.unpublished_root.id}
        ])

        # sidebar for child should contain published non-items children of articles in parent-path (to show active article)
        request_result = self.make_jsonrpc_request("/knowledge/public/sidebar", {'article_id': self.subchildren[0].id})
        self.assertEqual(request_result, [
            {'id': self.root_article.id, 'icon': '🐣', 'name': 'Published Root', 'parent_id': self.unpublished_root.id},
            {'id': self.root_children[0].id, 'icon': False, 'name': 'Published Child', 'parent_id': self.root_article.id},
            {'id': self.subchildren[0].id, 'icon': False, 'name': 'Published Subchild', 'parent_id': self.root_children[0].id},
            {'id': self.subchildren[1].id, 'icon': False, 'name': False, 'parent_id': self.root_children[0].id}])

        # sidebar for unpublished article should return nothing
        self.assertEqual(self.make_jsonrpc_request("/knowledge/public/sidebar", {'article_id': self.root_children[1].id}), [])

        # children route should only return published non item articles
        self.assertEqual(self.make_jsonrpc_request("/knowledge/public/children", {'article_id': self.root_article.id}), [
            {'id': self.root_children[0].id, 'name': 'Published Child', 'icon': False}
        ])

        # article search should only return published article with title matching the search term
        self.assertEqual(self.make_jsonrpc_request("/knowledge/public/search", {'subsite_root_id': self.root_article.id, 'search_value': "publish"}), [
            {'id': self.subchildren[0].id, 'name': 'Published Subchild', 'icon': False},
            {'id': self.root_children[2].id, 'name': 'Published Item', 'icon': False},
            {'id': self.root_children[0].id, 'name': 'Published Child', 'icon': False},
            {'id': self.root_article.id, 'name': 'Published Root', 'icon': '🐣'}])

    @users('custom_public_user')
    def test_knowledge_public_view_tour(self):
        self.start_tour('/knowledge/article/%s' % self.root_article.id, 'website_knowledge_public_view_tour')
