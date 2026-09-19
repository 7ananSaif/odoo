# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import HttpCase, new_test_user
from odoo.addons.spreadsheet_edition.tests.spreadsheet_test_case import SpreadsheetTestCase


class SpreadsheetMixinControllerTest(SpreadsheetTestCase, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.raoul = new_test_user(cls.env, login='raoul')

    def test_company_currency(self):
        self.authenticate(self.raoul.login, self.raoul.password)
        spreadsheet = self.env['spreadsheet.test'].create({})
        company_eur = self.env['res.company'].create({'currency_id': self.env.ref('base.EUR').id, 'name': 'EUR'})
        company_gbp = self.env['res.company'].create({'currency_id': self.env.ref('base.GBP').id, 'name': 'GBP'})
        self.raoul.company_ids |= company_eur | company_gbp

        self.opener.cookies['cids'] = f'{company_eur.id}-{company_gbp.id}'
        response = self.url_open(f'/spreadsheet/data/spreadsheet.test/{spreadsheet.id}')
        data = response.json()
        self.assertEqual(data['default_currency']['code'], 'EUR')
        self.assertEqual(data['default_currency']['symbol'], '€')

        self.opener.cookies['cids'] = f'{company_gbp.id}-{company_eur.id}'
        response = self.url_open(f'/spreadsheet/data/spreadsheet.test/{spreadsheet.id}')
        data = response.json()
        self.assertEqual(data['default_currency']['code'], 'GBP')
        self.assertEqual(data['default_currency']['symbol'], '£')

    def test_default_company_custom_colors(self):
        self.authenticate(self.raoul.login, self.raoul.password)
        spreadsheet = self.env['spreadsheet.test'].create({})
        company = self.env['res.company'].create({'name': 'test'})
        self.raoul.company_ids |= company
        self.opener.cookies['cids'] = str(company.id)
        response = self.url_open(f'/spreadsheet/data/spreadsheet.test/{spreadsheet.id}')
        data = response.json()
        self.assertEqual(data['company_colors'], ['#FFFFFF', '#875A7B'])

    def test_all_company_custom_colors(self):
        self.authenticate(self.raoul.login, self.raoul.password)
        spreadsheet = self.env['spreadsheet.test'].create({})
        company = self.env['res.company'].create({'name': 'test'})
        self.raoul.company_ids |= company
        self.opener.cookies['cids'] = str(company.id)
        company.primary_color = '#000000'
        company.secondary_color = '#ffffff'
        company.email_primary_color = '#aaaaaa'
        company.email_secondary_color = '#bbbbbb'
        response = self.url_open(f'/spreadsheet/data/spreadsheet.test/{spreadsheet.id}')
        data = response.json()
        self.assertEqual(data['company_colors'], ['#000000', '#ffffff', '#aaaaaa', '#bbbbbb'])

    def test_two_companies_custom_colors(self):
        self.authenticate(self.raoul.login, self.raoul.password)
        spreadsheet = self.env['spreadsheet.test'].create({})
        company_A = self.env['res.company'].create({'name': 'company A'})
        company_B = self.env['res.company'].create({'name': 'company B'})
        self.raoul.company_ids |= company_A | company_B
        self.opener.cookies['cids'] = f'{company_A.id}-{company_B.id}'
        company_A.primary_color = '#aa0000'
        company_B.primary_color = '#bb0000'
        company_A.secondary_color = '#aa1111'
        company_B.secondary_color = '#bb1111'
        response = self.url_open(f'/spreadsheet/data/spreadsheet.test/{spreadsheet.id}')
        data = response.json()
        self.assertEqual(data['company_colors'], ['#aa0000', '#aa1111', '#FFFFFF', '#875A7B', '#bb0000', '#bb1111'])
