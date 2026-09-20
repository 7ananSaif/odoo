# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import re

from contextlib import contextmanager
from lxml import etree
from unittest.mock import patch

from odoo.exceptions import RedirectWarning

from odoo.addons.l10n_ar.tests.common import TestAr
from odoo.tools.misc import file_open
from odoo.tools.zeep.exceptions import Fault
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestArConnection(TestAr):

    @contextmanager
    def mock_zeep_client(self, response, should_error=False):
        def create_fault_from_xml(xml_string):
            # Parse the XML string into an etree Element
            root = etree.fromstring(xml_string.encode())

            # Extract fault information from the XML
            # Typically, you need the faultcode and faultstring
            faultcode = root.find(".//faultcode").text if root.find(".//faultcode") is not None else "Client"
            faultstring = root.find(".//faultstring").text if root.find(".//faultstring") is not None else "Unknown error"

            # Create a Fault exception
            return Fault(
                message=faultstring,
                code=faultcode,
                actor=None,  # Optional
                detail=root  # You can pass the entire element as detail
            )

        class MockedService:
            def __init__(self, response):
                def create_endpoint(endpoint: str):
                    def call_endpoint(*args):
                        if should_error:
                            raise create_fault_from_xml(response)
                        return response
                    return call_endpoint

                self.loginCms = create_endpoint('loginCms')

        class MockedClient:
            def __init__(self, wsdl, transport):
                self.service = MockedService(response)
        with patch('odoo.addons.l10n_ar_edi.models.l10n_ar_afipws_connection.Client', new=MockedClient):
            yield

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ar_private_key = cls.env['certificate.key'].create({
            'name': 'AR Test Private key 1',
            'content': base64.b64encode(
                file_open("l10n_ar_edi/tests/private_key.pem", 'rb').read()
            ),
        })

        cls.ar_certificate_1 = cls.env['certificate.certificate'].create({
            'name': 'AR Test certificate 1',
            'content': base64.b64encode(
                file_open("l10n_ar_edi/tests/test_cert1.crt", 'rb').read()
            ),
            'private_key_id': cls.ar_private_key.id,
        })

        cls.company_ri.write({
            'l10n_ar_afip_ws_environment': 'testing',
            'l10n_ar_afip_ws_crt_id': cls.ar_certificate_1,
            'l10n_ar_afip_ws_key_id': cls.ar_private_key.id,
        })
        cls.env.user.write({'company_id': cls.company_ri.id})
        cls.config = cls.env['res.config.settings'].create({})

    def test_ar_connection_invalid(self):
        """ With no key content set, they will appear as expired or invalid. """

        private_content = self.ar_private_key.content
        cert_content = self.ar_certificate_1.content

        self.ar_certificate_1.content = ""
        self.ar_private_key.content = ""

        # Get the list of possible AR ARCA WebService connections. This allows us to know how many
        # elements in the regex we need to repeat for the search.
        conns_len = len(self.env['l10n_ar.afipws.connection']._get_l10n_ar_afip_ws())
        error_content = rf"(.*Connection failed.*\n?){{{conns_len}}}"

        with self.assertRaisesRegex(RedirectWarning, error_content):
            self.config.with_context(l10n_ar_invoice_skip_commit=True).l10n_ar_connection_test()

        login_response = """<?xml version="1.0" encoding="utf-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
          <soapenv:Body>
            <soapenv:Fault>
              <faultcode xmlns:ns1="http://xml.apache.org/axis/">ns1:cms.bad</faultcode>
              <faultstring>El CMS no es valido</faultstring>
              <detail>
                <ns2:exceptionName xmlns:ns2="http://xml.apache.org/axis/">LoginFault</ns2:exceptionName>
                <ns3:hostname xmlns:ns3="http://xml.apache.org/axis/">wsaaext0.homo.afip.gov.ar</ns3:hostname>
              </detail>
            </soapenv:Fault>
          </soapenv:Body>
        </soapenv:Envelope>
        """

        error_content = rf"(.*El CMS no es valido.*\n?){{{conns_len}}}"

        self.ar_private_key.content = private_content
        self.ar_certificate_1.content = cert_content

        with self.assertRaisesRegex(RedirectWarning, error_content):
            with self.mock_zeep_client(login_response, should_error=True):
                self.config.with_context(l10n_ar_invoice_skip_commit=True).l10n_ar_connection_test()

    def test_ar_connection_valid(self):
        """ Patch the Zeep client so it doesn't make a network call and appears valid """

        login_response = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <loginTicketResponse version="1.0">
            <credentials>
                <token>dummy</token>
                <sign>dummy</sign>
            </credentials>
        </loginTicketResponse>
        """
        # Get the list of possible AR ARCA WebService connections. This allows us to know how many
        # elements in the regex we need to repeat for the search.
        conns_len = len(self.env['l10n_ar.afipws.connection']._get_l10n_ar_afip_ws())
        error_content = rf"(.*Connection is available\n?){{{conns_len}}}"

        with self.assertRaisesRegex(RedirectWarning, error_content):
            with self.mock_zeep_client(login_response):
                self.config.with_context(l10n_ar_invoice_skip_commit=True).l10n_ar_connection_test()
