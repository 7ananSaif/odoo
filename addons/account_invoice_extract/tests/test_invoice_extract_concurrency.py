import contextlib
from unittest.mock import patch

from odoo import api

from odoo.exceptions import ConcurrencyError
from odoo.modules.registry import Registry
from odoo.tests.common import BaseCase, get_db_name, tagged
from odoo.tools import mute_logger

from odoo.addons.iap.tools import iap_tools
from odoo.addons.partner_autocomplete.models.iap_autocomplete_api import IapAutocompleteApi


@tagged('-standard', '-at_install', 'post_install', 'database_breaking')
class TestInvoiceExtractConcurrency(BaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registry = Registry(get_db_name())

    def test_no_duplicated_partner(self):
        partner_name = 'test_no_duplicated_partner'
        partner_vat = 'BE0477472701'
        extract_response = {
            'results': [{
                'VAT_Number': {'selected_value': {'content': partner_vat}, 'candidates': []},
            }],
            'status': 'success',
        }
        partner_autocomplete_response = {'data': {'name': partner_name, 'vat': partner_vat}}

        with contextlib.closing(self.registry.cursor()) as main_cr:
            main_env = api.Environment(main_cr, api.SUPERUSER_ID, {})
            invoice = main_env['account.move'].create({
                'move_type': 'in_invoice',
                'extract_state': 'waiting_extraction',
            })

            # Simulate a concurrent request creating an identical partner
            with self.registry.cursor() as cr:
                env = api.Environment(cr, api.SUPERUSER_ID, {})
                partner = env['res.partner'].create({
                    'name': partner_name,
                    'vat': partner_vat,
                    'is_created_by_ocr': True,
                })

                def unlink(partner):
                    with self.registry.cursor() as cr:
                        partner.with_env(partner.env(cr=cr)).unlink()
                self.addCleanup(unlink, partner)

            with (
                patch.object(iap_tools, 'iap_jsonrpc', return_value=extract_response),
                patch.object(IapAutocompleteApi, '_contact_iap', return_value=partner_autocomplete_response),
                mute_logger('odoo.sql_db'),
                self.assertRaises(ConcurrencyError, msg="The concurrent partner creation should be detected"),
            ):
                invoice._check_ocr_status()
