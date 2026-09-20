from odoo.tests import tagged
from odoo.addons.base.tests.common import HttpCase


@tagged('-at_install', 'post_install')
class TestDatabasesUi(HttpCase):

    def test_ui(self):
        self.start_tour('/odoo', 'databases_tour', login='admin')
