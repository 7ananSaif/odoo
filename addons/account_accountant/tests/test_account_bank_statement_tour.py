from requests import Session, PreparedRequest, Response

from .common import TestBankRecWidgetCommon
from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestAccountBankStatementTour(TestBankRecWidgetCommon, HttpCase):

    @classmethod
    def _request_handler(cls, s: Session, r: PreparedRequest, /, **kw):
        # mock odoofin requests
        if 'proxy/v2/get_dashboard_institutions' in r.url:
            r = Response()
            r.status_code = 200
            r.json = list
            return r
        return super()._request_handler(s, r, **kw)

    def test_tour_bank_rec_widget(self):
        self.partner_a.name = "AAAA"  # To have this partner as the first one in the list
        self._create_invoice_line('out_invoice', partner_id=self.partner_a.id, invoice_line_ids=[{'price_unit': 100.0}])
        self._create_invoice_line('out_invoice', partner_id=self.partner_a.id, invoice_line_ids=[{'price_unit': 150.0}])
        self.start_tour('/odoo', 'account_accountant_bank_rec_widget', login=self.env.user.login)

    def test_tour_bank_reconciliation_widget_reload_activities_when_add_a_new_one(self):
        self._create_st_line(amount=100.0)

        self.start_tour('/odoo', 'account_accountant_bank_reconciliation_widget_reload_activies_when_add_a_new_one', login=self.env.user.login)
