from lxml import etree

from odoo import Command

from odoo.addons.accountant_knowledge.controller.main import is_html_element_empty
from odoo.addons.base.tests.common import TransactionCaseWithUserDemo


class TestAccountantKnowledgeAuditReport(TransactionCaseWithUserDemo):
    def test_automatically_invite_responsible_users_on_root_article(self):
        """ Check that the responsible users are automatically invited to the
            article linked to the audit report. """

        audit_report = self.env['audit.report'].create({
            'title': 'My Audit Report',
            'responsible_user_ids': [
                Command.link(self.user_demo.id)
            ],
        })

        article = audit_report.knowledge_article_id
        self.assertEqual(len(article.article_member_ids), 2)
        self.assertEqual(article.article_member_ids[0].partner_id, self.env.user.partner_id)
        self.assertEqual(article.article_member_ids[0].permission, 'write')
        self.assertEqual(article.article_member_ids[1].partner_id, self.user_demo.partner_id)
        self.assertEqual(article.article_member_ids[1].permission, 'write')

    def test_is_html_element_empty(self):
        """ Check that the `is_html_element_empty` method correctly identifies
            empty HTML elements, ignoring all empty tags and whitespace
            characters."""
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div></div>
        ''')))
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div>   </div>
        ''')))
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div><div></div></div>
        ''')))
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div><div> </div></div>
        ''')))
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div><div> </div> </div>
        ''')))
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div> <div> </div> </div>
        ''')))
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div><p><br/></p></div>
        ''')))
        # NBSP character (\u00A0):
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div><p>&#160;<br/></p></div>
        ''')))

        self.assertFalse(is_html_element_empty(etree.fromstring('''
            <div>Hello</div>
        ''')))
        self.assertFalse(is_html_element_empty(etree.fromstring('''
            <div><p>Hello<br/></p></div>
        ''')))
