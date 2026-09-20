# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from pprint import pformat

from odoo import models, api, fields, _, Command
from odoo.addons.account_avatax.lib.avatax_client import AvataxClient
from odoo.exceptions import UserError, ValidationError, RedirectWarning
from odoo.release import version
from odoo.tools import float_round

_logger = logging.getLogger(__name__)


class AccountExternalTaxMixin(models.AbstractModel):
    _inherit = 'account.external.tax.mixin'

    # Technical field used for the visibility of fields and buttons
    is_avatax = fields.Boolean(compute='_compute_is_avatax')

    @api.depends('fiscal_position_id')
    def _compute_is_avatax(self):
        for record in self:
            record.is_avatax = record.fiscal_position_id.is_avatax

    def _compute_is_tax_computed_externally(self):
        super()._compute_is_tax_computed_externally()
        self.filtered('is_avatax').is_tax_computed_externally = True

    @api.constrains('partner_id', 'fiscal_position_id')
    def _check_address(self):
        incomplete_partner_to_records = {}
        for record in self.filtered(lambda r: r.is_avatax and r._get_avatax_service_params()['perform_address_validation']):
            partner = record.partner_id
            country = partner.country_id
            if (
                partner and partner != self.env.ref('base.public_partner')
                and (
                    not country
                    or (country.zip_required and not partner.zip)
                    or (country.state_required and not partner.state_id)
                )
            ):
                incomplete_partner_to_records.setdefault(partner, []).append(record)

        if incomplete_partner_to_records:
            error = _("The following customer(s) need to have a zip, state and country when using Avatax:")
            partner_errors = [
                self.env._(
                    "- %(partner_name)s (ID: %(partner_id)s) on %(record_list)s",
                    partner_name=partner.display_name,
                    partner_id=partner.id,
                    record_list=[record.display_name for record in records],
                )
                for partner, records in incomplete_partner_to_records.items()
            ]
            raise ValidationError(error + "\n" + "\n".join(partner_errors))

    def _get_avatax_service_params(self, commit=False):
        params = self._get_external_tax_service_params()
        params.update({
            'commercial_partner': self.partner_id.commercial_partner_id.with_company(self.company_id),
            'shipping_partner': self.partner_shipping_id or self.partner_id,
            'unique_code': self.avatax_unique_code,
            'reference': self.name,
            'currency': self.currency_id,
            'commit': commit and self._find_avatax_credentials_company(self.company_id).avalara_commit,
            'fiscal_position': self.fiscal_position_id,

            # To be filled by specific models
            'is_refund': None,
            'document_type': None,
            'tax_date': None,
            'perform_address_validation': None,
        })
        return params

    @api.model
    def _prepare_avatax_document_line_service_call(self, line_data, is_refund):
        """Create a `LineItemModel` based on line_data.

        :param dict line_data: base line data returned by _get_line_data_for_external_taxes()
        """
        base_line = line_data['base_line']
        product = base_line['product_id']
        avatax_category = product._get_avatax_category_id()
        if not avatax_category:
            raise UserError(_(
                'The Avalara Tax Code is required for %(name)s (#%(id)s)\n'
                'See https://taxcode.avatax.avalara.com/',
                name=product.display_name,
                id=product.id,
            ))
        item_code = f'UPC:{product.barcode}' if base_line['record'].company_id.avalara_use_upc and product.barcode else product.code
        subtotal = base_line['tax_details']['total_excluded_currency']
        return {
            'amount': -subtotal if is_refund else subtotal,
            'description': line_data['description'],
            'quantity': abs(base_line['quantity']),
            'taxCode': avatax_category.code,
            'itemCode': item_code,
            'number': "%s,%s" % (base_line['record']._name, base_line['id']),
        }

    @api.model
    def _get_avatax_address(self, partner):
        if all(partner._fields[field] for field in ['zip', 'state_id', 'country_id']):
            return {
                'city': partner.city,
                'country': partner.country_id.code,
                'region': partner.state_id.code,
                'postalCode': partner.zip,
                'line1': partner.street,
            }
        else:
            return {
                'latitude': partner.partner_latitude,
                'longitude': partner.partner_longitude,
            }

    @api.model
    def _prepare_avatax_document_service_call(self, params):
        """Get the transaction values.

        :returns: a mapping defined by the AvataxModel ``CreateTransactionModel``.
        :rtype: dict
        """
        lines = [self._prepare_avatax_document_line_service_call(line_data, params['is_refund']) for line_data in params['line_data']]
        res = {
            'addresses': {
                'shipFrom': self._get_avatax_address(params['company_partner']),
                'shipTo': self._get_avatax_address(params['shipping_partner']),
            },
            'companyCode': params['company_partner'].avalara_partner_code or '',
            'customerCode': params['commercial_partner'].avalara_partner_code or params['commercial_partner'].avatax_unique_code,
            'entityUseCode': params['commercial_partner'].avalara_exemption_id.code or '',
            'businessIdentificationNo': params['commercial_partner'].vat or '',
            'date': (params['document_date'] or fields.Date.today()).isoformat(),
            'type': params['document_type'],
            'code': params['unique_code'],
            'referenceCode': params['reference'],
            'currencyCode': params['currency'].name or '',
            'commit': params['commit'],
            'lines': lines,
        }

        if params['tax_date']:
            res['taxOverride'] = {
                'type': 'taxDate',
                'reason': 'Manually changed the tax calculation date',
                'taxDate': params['tax_date'].isoformat(),
            }

        return res

    @api.model
    def _extract_tax_values_from_avatax_detail(self, service_params, line_details, tax_detail):
        company = service_params['line_data'][0]['base_line']['record'].company_id
        fiscal_position = service_params['fiscal_position']
        amount_type = 'fixed' if tax_detail.get('unitOfBasis') == 'FlatAmount' else 'percent'
        amount = tax_detail['rate'] * (1 if amount_type == 'fixed' else 100)

        rounded_amount = float_round(amount, precision_digits=4)
        tax_group_name = tax_detail['taxName'].removesuffix(' TAX')
        if amount_type == 'fixed':
            tax_name_suffix = "$ %.4g" % rounded_amount
        else:
            tax_name_suffix = "%.4g%%" % rounded_amount

        tax_name = f"{tax_group_name} {tax_name_suffix}"

        is_return = service_params['document_type'] == 'ReturnInvoice'
        line_amount_sign = -1 if is_return else 1

        tax_amount = tax_detail['tax'] * line_amount_sign
        return (
            {'name': tax_group_name, 'company_id': company.id},
            {
                'name': tax_name,
                'company_id': company.id,
                'amount': amount,
                'amount_type': amount_type,
                'invoice_repartition_line_ids': [
                    Command.create({'repartition_type': 'base'}),
                    Command.create({'repartition_type': 'tax', 'account_id': fiscal_position.avatax_invoice_account_id.id}),
                ],
                'refund_repartition_line_ids': [
                    Command.create({'repartition_type': 'base'}),
                    Command.create({'repartition_type': 'tax', 'account_id': fiscal_position.avatax_refund_account_id.id}),
                ],
            },
            {'tax_amount_currency': tax_amount}
        )

    def _get_external_taxes(self):
        # EXTENDS 'account.external.tax.mixin'
        res = super()._get_external_taxes()
        errors = []

        for company, records in self.filtered('is_avatax').grouped("company_id").items():
            base_line_with_tax_values = []
            client = self._get_client(company)

            for record in records:
                service_params = record._get_avatax_service_params()

                # Avatax errors when sending records without lines
                if not service_params['line_data']:
                    continue

                document_data = record._prepare_avatax_document_service_call(service_params)
                base_lines = [data['base_line'] for data in service_params['line_data']]

                api_response = client.create_transaction(document_data, include='Lines')
                error = self._handle_response(api_response, _(
                    'Odoo could not fetch the taxes related to %(document)s.\n'
                    'Please check the status of `%(technical)s` in the AvaTax portal.',
                    document=record.display_name,
                    technical=record.avatax_unique_code,
                ))
                if error:
                    errors.append(error)
                    continue

                for base_line, line_results in zip(base_lines, api_response['lines']):
                    tax_values_list = []
                    for tax_detail in line_results['details']:
                        tax_values_list.append(self._extract_tax_values_from_avatax_detail(service_params, line_results, tax_detail))
                    base_line_with_tax_values.append((base_line, tax_values_list))

            if errors:
                raise UserError('\n\n'.join(errors))

            res.update(self._process_external_taxes(company, base_line_with_tax_values, 'name'))

        return res

    def _change_avatax_state(self, action):
        assert action in ('commit', 'uncommit', 'void')

        for company, records in self.filtered('is_avatax').grouped('company_id').items():
            company_commit = self._find_avatax_credentials_company(company).avalara_commit
            if not company_commit and 'commit' in action:
                continue

            client = self._get_client(company)

            for record in records:
                params = {
                    'companyCode': record.company_id.partner_id.avalara_partner_code,
                    'transactionCode': record.avatax_unique_code
                }
                if action == 'commit':
                    query_result = client.commit_transaction(**params)
                elif action == 'uncommit':
                    query_result = client.uncommit_transaction(**params)
                else:  # void
                    query_result = client.void_transaction(**params)

                    # There's nothing to void when a draft record is deleted without ever being sent to Avatax.
                    if query_result.get('error', {}).get('code') == 'EntityNotFoundError':
                        _logger.info(pformat(query_result))
                        continue

                error = self._handle_response(query_result, _(
                    'Odoo could not change the state of the transaction related to %(document)s in'
                    ' AvaTax\nPlease check the status of `%(technical)s` in the AvaTax portal.',
                    document=record.display_name,
                    technical=record.avatax_unique_code,
                ))
                if error:
                    raise UserError(error)

    def _commit_avatax_taxes(self):
        self._change_avatax_state('commit')

    def _uncommit_external_taxes(self):
        self._change_avatax_state('uncommit')
        return super()._uncommit_external_taxes()

    def _void_external_taxes(self):
        self._change_avatax_state('void')
        return super()._void_external_taxes()

    def _handle_response(self, response, title):
        if response.get('errors'):  # http error
            _logger.warning(pformat(response), stack_info=True)
            return '%s\n%s' % (title, response.get('title', ''))

        if response.get('error'):  # avatax error
            _logger.warning(pformat(response), stack_info=True)
            messages = '\n'.join(detail['message'] for detail in response['error']['details'])
            return '%s\n%s' % (title, messages)

        return None

    @api.model
    def _find_avatax_credentials_company(self, company):
        has_avatax_credentials = company.sudo().avalara_api_id and company.sudo().avalara_api_key
        if has_avatax_credentials:
            return company
        elif company.parent_id:
            return self._find_avatax_credentials_company(company.parent_id)
        return None

    def _get_client(self, company):
        company = self._find_avatax_credentials_company(company)
        if not company:
            raise RedirectWarning(
                _('Please add your AvaTax credentials'),
                self.env.ref('base_setup.action_general_configuration').id,
                _("Go to the configuration panel"),
            )

        client = AvataxClient(
            app_name='Odoo',
            app_version=version,
            environment=company.avalara_environment,
        )
        client.add_credentials(
            company.sudo().avalara_api_id or '',
            company.sudo().avalara_api_key or '',
        )
        client.logger = lambda message: self._log_external_tax_request(
            'Avatax US', 'account_avatax.log.end.date', message
        )
        return client
