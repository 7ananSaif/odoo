# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import HttpCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestSearchbarKnowledgeArticles(HttpCase):

    def test_search_within_knowledge_articles(self):
        self.env["knowledge.article"].create([{
            "name": "Test Filter knowledge Article",
            "is_article_visible_by_everyone": True,
            "website_published": True
        }])
        self.start_tour(self.env["website"].get_client_action_url("/"), "test_searchbar_within_knowledge_articles", login="admin")
