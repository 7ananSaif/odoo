import csv
import logging
import uuid
import secrets
import string

from odoo import _, api, models, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tools import file_open

from odoo.addons.hr_expense_stripe.controllers.main import StripeIssuingController
from odoo.addons.hr_expense_stripe.utils import COUNTRY_MAPPING, STRIPE_VALID_JOURNAL_CURRENCIES, make_request_stripe_proxy


_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Stripe account
    stripe_id = fields.Char(string="Stripe Account ID", copy=False, groups='base.group_system')
    stripe_account_issuing_status = fields.Selection(
        selection=[
            ('restricted', "Restricted"),
            ('verified', "Verified"),
        ],
        string="Status",
        default='restricted',
    )

    stripe_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Stripe Issuing Journal",
        domain=[('type', '=', 'bank'), ('bank_statements_source', '=', 'stripe_issuing')],
        check_company=True,
        copy=False,
    )
    stripe_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string="Stripe Currency",
        compute='_compute_stripe_currency',
        store=True,
        readonly=True,
        copy=False,
    )
    stripe_issuing_activated = fields.Boolean(readonly=True)
    stripe_account_issuing_tos_accepted = fields.Boolean(groups='base.group_system')
    stripe_account_issuing_tos_acceptance_date = fields.Date(groups='base.group_system')
    stripe_issuing_iap_webhook_uuid = fields.Char(groups='base.group_system')

    # IAP Security fields
    stripe_issuing_db_private_key_id = fields.Many2one(
        comodel_name='certificate.key',
        readonly=True,
        groups='base.group_system',
        copy=False,
    )
    stripe_issuing_iap_public_key_id = fields.Many2one(
        comodel_name='certificate.key',
        readonly=True,
        groups='base.group_system',
        copy=False,
    )

    _constraint_journal_stripe_activated = models.Constraint(
        definition="CHECK(NOT stripe_issuing_activated OR (stripe_journal_id IS NOT NULL AND stripe_issuing_activated))",
        message="You cannot remove the journal used by Stripe Issuing when it is activated",
    )

    @api.depends('country_id', 'account_fiscal_country_id')
    def _compute_stripe_currency(self):
        for company in self:
            company_country = company.account_fiscal_country_id
            if 'EU' in (company_country.country_group_codes or []):
                company_currency_code = STRIPE_VALID_JOURNAL_CURRENCIES['EU']
            elif company_country.code == 'gb':
                company_currency_code = STRIPE_VALID_JOURNAL_CURRENCIES['UK']
            else:
                company_currency_code = STRIPE_VALID_JOURNAL_CURRENCIES.get(company_country.code) or 'USD'
            currency = self.env['res.currency'].search([('name', '=ilike', company_currency_code)], limit=1)
            company.stripe_currency_id = currency and currency.id

    def _stripe_issuing_setup_mcc(self):
        """ Helper to preset the default data for the mccs on all company as the field is company_dependant """
        # Fetch all the MCC data and create a mapping of the references to the respective records
        mcc_data = self.env['ir.model.data']._read_group(
            [('model', '=', 'product.mcc.stripe.tag')],
            groupby=['name'],
            aggregates=['res_id:array_agg'],  # Can't use recordset because it's not a Many2one field but a ref
        )
        ref_to_mcc = {}
        mcc_prefetch_ids = []
        for ref, (res_id,) in mcc_data:
            mcc_prefetch_ids.append(res_id)
            ref_to_mcc[ref] = self.env['product.mcc.stripe.tag'].browse(res_id).with_prefetch(mcc_prefetch_ids)

        # Read the file data to know what referenced products to fetch and create a mapping of mcc references to product references
        products_referenced = set()
        mcc_ref_to_product_ref = {}
        with file_open('hr_expense_stripe/data/template/product.mcc.stripe.tag.csv', 'rt') as csv_file:
            for row in csv.DictReader(csv_file):
                product_ref_name = row['product_id'].split('.', 1)[-1]
                mcc_ref_to_product_ref[row['id']] = product_ref_name
                products_referenced.add(product_ref_name)

        # Fetch the products data and map the references to their respective records
        product_data = self.env['ir.model.data']._read_group(
            [('model', '=', 'product.product'), ('name', 'in', tuple(products_referenced))],
            groupby=['name'],
            aggregates=['res_id:array_agg'],  # Can't use recordset because it's not a Many2one field but a ref
        )
        ref_to_product = {}
        product_prefetch_ids = []
        for ref, (res_id,) in product_data:
            product_prefetch_ids.append(res_id)
            ref_to_product[ref] = self.env['product.product'].browse(res_id).with_prefetch(product_prefetch_ids)

        # Now we can iterate over all companies and set the products on the MCCs
        available_to_all_companies = self.browse()  # Empty value means all companies
        for company in self:
            for mcc_ref, product_ref in mcc_ref_to_product_ref.items():
                mcc = ref_to_mcc.get(mcc_ref).with_company(company)
                product = ref_to_product.get(product_ref)
                if mcc and not mcc.product_id and product and product.company_id in {available_to_all_companies, company}:
                    mcc.product_id = product.id

    def _get_account_links_payload(self):
        """ Helper for stripe onboarding payload, to ensure we go back to the settings
        :return: Stripe Payload
        :rtype: dict[str, str]
        """
        self.ensure_one()
        return {
            'account': self.stripe_id,
            'refresh_url': f"{self.get_base_url()}/odoo/settings#hr_expense",
            'return_url': f"{self.get_base_url()}/odoo/settings#hr_expense",
        }

    def _get_stripe_webhook_url(self, uuid=None):
        """ Helper to get the full webhook URL for this database

        :param str|None uuid: Override the database webhook ID part
        :return: Database webhook URL
        :rtype: str
        """
        self.ensure_one()
        return '/'.join((self.get_base_url(), StripeIssuingController._webhook_url, uuid or self.stripe_issuing_iap_webhook_uuid))

    @api.model
    def _get_stripe_mode(self):
        key = 'hr_expense_stripe.stripe_mode'
        mode = self.env['ir.config_parameter'].sudo().get_param(key, 'live')
        if mode not in {'live', 'test'}:
            raise ValidationError(_("System parameter '%(name)s' value is incorrect, expecting 'live', 'test' or no value", name=key))
        return mode

    def _create_stripe_issuing_journal(self):
        """ Helper function to create the default issuing journal automatically """
        for company in self:
            ChartTemplate = self.env['account.chart.template'].with_company(company)
            journal = ChartTemplate.ref('stripe_issuing_journal', raise_if_not_found=False)
            if not company.stripe_currency_id:
                continue
            if not journal:
                self.env['account.journal'].with_company(company)._load_records([
                    {
                        'xml_id': f"account.{company.id}_{xml_id}",
                        'values': values,
                        'noupdate': True,
                    }
                    for xml_id, values in ChartTemplate._get_stripe_issuing_account_journal(None).items()
                ])
                journal = ChartTemplate.ref('stripe_issuing_journal')
            if not journal.active:
                journal.active = True
            if not company.stripe_journal_id:
                company.stripe_journal_id = journal

    def _cron_refresh_stripe_account(self):
        """ Cron job to refresh the status of all Stripe accounts """
        for company in self.env['res.company'].search([('stripe_id', '!=', False)]):
            company.action_refresh_stripe_account()

    def action_create_stripe_account(self):
        """ Create a stripe Connect account and redirects to the Stripe Onboarding """
        self.ensure_one()
        if self.stripe_id:
            return self.action_configure_stripe_account()

        if self.stripe_issuing_iap_webhook_uuid:
            raise UserError(_("A Webhook URL already exists for this company."))

        if not self.stripe_journal_id:
            # Create the default journal if not already done
            self._create_stripe_issuing_journal()
            self.stripe_journal_id = self.env.ref(f'account.{self.id}_stripe_issuing_journal')

        if not self.stripe_journal_id.currency_id:
            self.stripe_journal_id.currency_id = self.stripe_currency_id

        printable_characters_no_spaces = string.digits + string.ascii_letters + string.punctuation
        random_password = ''.join(secrets.choice(printable_characters_no_spaces) for _i in range(36))
        db_private_key = self.env['certificate.key']._generate_ed25519_private_key(
            company=self,
            name=_("Private key used for Stripe Issuing"),
            password=random_password,
        )
        stripe_issuing_iap_webhook_uuid = str(uuid.uuid4())
        payload = {
            'country': COUNTRY_MAPPING.get(self.country_id.code, self.country_id.code),
            'email': self.email,
            'business_type': 'company',
            'company[address][city]': self.city,
            'company[address][country]': COUNTRY_MAPPING.get(self.country_id.code, self.country_id.code),
            'company[address][line1]': self.street,
            'company[address][line2]': self.street2,
            'company[address][postal_code]': self.zip,
            'company[address][state]': self.state_id.name,
            'company[name]': self.name,
            'business_profile[name]': self.name,

            # IAP Data
            'db_webhook_url': self._get_stripe_webhook_url(stripe_issuing_iap_webhook_uuid),
            'db_public_key': db_private_key._get_public_key_bytes().decode(),
            'db_uuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid'),
            'accepted_tos': self.stripe_account_issuing_tos_accepted,
        }
        payload = {key: value for key, value in payload.items() if value is not False}
        response = make_request_stripe_proxy(self.sudo(), 'accounts', payload=payload, method='POST')
        iap_public_key = self.env['certificate.key'].create([{
            'name': _("IAP Public key used for Stripe Issuing"),
            'content': response['iap_public_key'],
            'company_id': self.id,
        }])
        self.write({
            'stripe_id': response['id'],
            'stripe_issuing_iap_webhook_uuid': stripe_issuing_iap_webhook_uuid,
            'stripe_account_issuing_tos_accepted': True,
            'stripe_account_issuing_tos_acceptance_date': fields.Date.today(),
            'stripe_issuing_db_private_key_id': db_private_key.id,
            'stripe_issuing_iap_public_key_id': iap_public_key.id,
        })
        self.env['ir.config_parameter'].sudo().set_param(f'hr_expense_stripe.{self.id}_stripe_issuing_pk', response['stripe_pk'])

        self.stripe_issuing_activated = True
        cron = self.env.ref('hr_expense_stripe.hr_expense_stripe_issuing_status_cron', raise_if_not_found=False)
        if cron and not cron.active:
            cron.active = True

        return self.action_configure_stripe_account()

    def action_refresh_stripe_account(self):
        """ Refreshes the status of the Stripe account, when pending validation from stripe.
        It also updates the public key"""
        for company in self:
            response = make_request_stripe_proxy(
                company.sudo(),
                'accounts/{account}',
                route_params={'account': company.sudo().stripe_id},
                method='GET',
            )

            if response['capabilities']['card_issuing'] == 'active':
                company.stripe_account_issuing_status = 'verified'
            else:
                company.stripe_account_issuing_status = 'restricted'

            current_pk = company.env['ir.config_parameter'].sudo().get_param(f'hr_expense_stripe.{company.id}_stripe_issuing_pk')
            if current_pk != response['stripe_pk']:
                company.env['ir.config_parameter'].sudo().set_param(
                    f'hr_expense_stripe.{company.id}_stripe_issuing_pk',
                    response['stripe_pk'],
                )

    def action_configure_stripe_account(self):
        """ Action to go back to an interrupted Stripe Onboarding """
        self.ensure_one()

        if not self.sudo().stripe_id:
            raise ValidationError(_("You need to be connected to stripe in order to configure your account."))

        payload = self._get_account_links_payload()
        response = make_request_stripe_proxy(self.sudo(), 'account_links', payload=payload, method='POST')
        return {
            'type': 'ir.actions.act_url',
            'url': response['url'],
            'target': 'self',
        }
