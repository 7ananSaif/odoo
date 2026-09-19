# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo.tests.common import HttpCase, new_test_user


class SaleOrderSpreadsheet(HttpCase):

    def test_create_spreadsheet(self):
        raoul = new_test_user(self.env, login='raoul', groups='sales_team.group_sale_salesman')
        self.authenticate(raoul.login, raoul.password)
        spreadsheet = self.env['sale.order.spreadsheet'].create({'name': 'spreadsheet'})
        response = self.url_open('/spreadsheet/data/sale.order.spreadsheet/%s' % spreadsheet.id)
        data = response.json()['data']
        self.assertTrue(data['lists'])
        self.assertTrue(data['globalFilters'])
        revision = spreadsheet.spreadsheet_revision_ids
        self.assertEqual(len(revision), 1)
        commands = json.loads(revision.commands)['commands']
        self.assertEqual(commands[0]['type'], 'RE_INSERT_ODOO_LIST')
        self.assertEqual(commands[1]['type'], 'CREATE_TABLE')
