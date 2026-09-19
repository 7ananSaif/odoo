from io import BytesIO
from freezegun import freeze_time
from zipfile import ZipFile

from odoo.tests.common import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingHttpCommon
from .common import TestEcEdiCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPortalWithholding(TestEcEdiCommon, AccountTestInvoicingHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner_vals = {
            'name': "EC Test Partner AàÁ³$£€èêÈÊöÔÇç¡⅛&@™",  # special characters should be escaped appropriately
            'street': "Av. Libertador Simón Bolívar 1155",
            'zip': "170209",
            'city': "Quito",
            'country_id': cls.env.ref('base.ec').id,
            'vat': "0453661050152",
            'l10n_latam_identification_type_id': cls.env.ref('l10n_ec.ec_ruc').id,
        }
        cls.user_portal = cls._create_new_portal_user(**partner_vals)
        cls.portal_partner = cls.user_portal.partner_id

    def test_portal_withhold_detail_not_their_withholding(self):
        """ Creates a withholding for a vendor bill for a different user
        and makes sure that the portal user doesn't have access to the document.
        The user should be redirected to their portal home.
        """
        wizard, purchase_invoice = self.get_wizard_and_purchase_invoice()
        with freeze_time(self.frozen_today):
            withhold = wizard.action_create_and_post_withhold()
        self.assertEqual(withhold.state, 'posted')

        purchase_invoice._compute_l10n_ec_withhold_inv_fields()

        url = f'/my/invoices/{withhold.id}?report_type=pdf&download=True'
        self.authenticate(self.user_portal.login, self.user_portal.login)
        res = self.url_open(url)
        self.assertEqual(res.request.path_url, '/my', 'User was not redirected to home')
        self.assertEqual(res.status_code, 200)

    def test_portal_withhold_detail_download_pdf(self):
        """ Creates a withholding for a vendor bill for the portal user that can be downloaded
        from the page. Since there is no edi processing ran it only downloads the PDF.
        """
        wizard, purchase_invoice = self.get_wizard_and_purchase_invoice(
            partner_id=self.portal_partner.id
        )
        with freeze_time(self.frozen_today):
            withhold = wizard.action_create_and_post_withhold()
        self.assertEqual(withhold.state, 'posted')
        purchase_invoice._compute_l10n_ec_withhold_inv_fields()

        action = withhold.l10n_ec_action_send_withhold()
        wizard = self.env[action['res_model']].with_context(action['context']).create({})
        wizard.action_send_and_print()

        url = f'/my/invoices/{withhold.id}?report_type=pdf&download=True'
        self.authenticate(self.user_portal.login, self.user_portal.login)
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, withhold.invoice_pdf_report_id.raw)

    def test_portal_withhold_detail_download_zip(self):
        """ Creates a withholding for a vendor bill for the portal user that can be downloaded
        from the page. By processing the edi document first we should get a zip file that contains
        both the PDF and Edi XML document.
        """
        wizard, purchase_invoice = self.get_wizard_and_purchase_invoice(
            partner_id=self.portal_partner.id
        )
        with freeze_time(self.frozen_today):
            withhold = wizard.action_create_and_post_withhold()
        self.assertEqual(withhold.state, 'posted')
        purchase_invoice._compute_l10n_ec_withhold_inv_fields()
        withhold.action_process_edi_web_services(with_commit=False)

        action = withhold.l10n_ec_action_send_withhold()
        wizard = self.env[action['res_model']].with_context(action['context']).create({})
        wizard.action_send_and_print()

        url = f'/my/invoices/{withhold.id}?report_type=pdf&download=True'
        self.authenticate(self.user_portal.login, self.user_portal.login)
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200)

        file_names = [doc['filename'] for doc in withhold._get_invoice_legal_documents_all()]
        with ZipFile(BytesIO(res.content)) as zip_file:
            self.assertEqual(
                zip_file.namelist(),
                file_names,
            )
