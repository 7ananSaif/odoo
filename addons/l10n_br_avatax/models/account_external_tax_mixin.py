# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from datetime import datetime
from json import dumps
from pprint import pformat

from odoo import models, fields, _, api
from odoo.addons.iap.tools.iap_tools import iap_jsonrpc
from odoo.addons.l10n_br_avatax.models.product_template import USE_TYPE_SELECTION
from odoo.exceptions import ValidationError
from odoo.tools import partition
from odoo.tools.float_utils import float_round, json_float_round

logger = logging.getLogger(__name__)

IAP_SERVICE_NAME = 'l10n_br_avatax_proxy'
DEFAULT_IAP_ENDPOINT = 'https://l10n-br-avatax.api.odoo.com'
DEFAULT_IAP_TEST_ENDPOINT = 'https://l10n-br-avatax.test.odoo.com'
ICP_LOG_NAME = 'l10n_br_avatax.log.end.date'
AVATAX_PRECISION_DIGITS = 2  # defined by API


class AccountExternalTaxMixin(models.AbstractModel):
    """ Brazilian Avatax adaptations. This class requires the following fields on the inherited model:
    - company_id (res.company): the company the record belongs to,
    - country_code (Char): the country code of the company this record belongs to,
    - fiscal_position_id (account.fiscal.position): fiscal position used for this record,
    - currency_id (res.currency): currency used on the record,
    - partner_shipping_id (res.partner): delivery address, where services are rendered or goods are delivered,
    - partner_id (res.partner): the end customer of the transaction,
    """
    _inherit = 'account.external.tax.mixin'

    l10n_br_is_service_transaction = fields.Boolean(
        "Is Service Transaction",
        compute="_compute_l10n_br_is_service_transaction",
        help="Technical field used to determine if this transaction should be sent to the service or goods API.",
    )
    l10n_br_cnae_code_id = fields.Many2one(
        "l10n_br.cnae.code",
        string="CNAE Code",
        compute="_compute_l10n_br_cnae_code_id",
        store=True,
        readonly=False,
        help="Brazil: the company's CNAE code for tax calculation and EDI."
    )
    l10n_br_goods_operation_type_id = fields.Many2one(
        "l10n_br.operation.type",
        compute="_compute_l10n_br_goods_operation_type_id",
        store=True,
        readonly=False,
        copy=False,
        string="Goods Operation Type",
        help="Brazil: this is the operation type related to the goods transaction. This will be used as a default on transaction lines."
    )
    l10n_br_use_type = fields.Selection(
        USE_TYPE_SELECTION,
        string="Purpose of Use",
        help="Brazil: this will override the purpose of use for all products sold here."
    )
    l10n_br_is_avatax = fields.Boolean(
        compute="_compute_l10n_br_is_avatax",
        string="Is Brazilian Avatax",
        help="Technical field used to check if this record requires tax calculation or EDI via Avatax."
    )
    # Technical field that holds errors meant for the actionable_errors widget.
    l10n_br_avatax_warnings = fields.Json(compute="_compute_l10n_br_avatax_warnings")

    def _compute_l10n_br_is_service_transaction(self):
        """Should be overridden. Used to determine if we should treat this record as a service (NFS-e) record."""
        self.l10n_br_is_service_transaction = False

    @api.depends('company_id')
    def _compute_l10n_br_cnae_code_id(self):
        for record in self:
            record.l10n_br_cnae_code_id = self.company_id.l10n_br_cnae_code_id

    @api.depends('country_code', 'fiscal_position_id')
    def _compute_l10n_br_goods_operation_type_id(self):
        """Set the default operation type which is standardSales. Should be overridden to determine
        the document type for the model."""
        for record in self:
            record.l10n_br_goods_operation_type_id = self.env.ref("l10n_br_avatax.operation_type_1") if record._l10n_br_is_avatax() else False

    def _compute_l10n_br_is_avatax_depends(self):
        return ['country_code', 'fiscal_position_id']

    @api.depends(lambda self: self._compute_l10n_br_is_avatax_depends())
    def _compute_l10n_br_is_avatax(self):
        for record in self:
            record.l10n_br_is_avatax = record._l10n_br_is_avatax()

    def _compute_is_tax_computed_externally(self):
        super()._compute_is_tax_computed_externally()
        self.filtered(lambda record: record.l10n_br_is_avatax).is_tax_computed_externally = True

    def _l10n_br_is_avatax(self):
        return self.country_code == 'BR' and self.fiscal_position_id.l10n_br_is_avatax

    def _depends_l10n_br_avatax_warnings(self):
        """Provides dependencies that trigger recomputation of l10n_br_avatax. Model-specific fields should be added
        with an override."""
        return ["l10n_br_is_avatax", "l10n_br_is_service_transaction", "currency_id", "company_id"]

    def _l10n_br_avatax_check_company(self):
        company_sudo = self.company_id.sudo()
        api_id, api_key = company_sudo.l10n_br_avatax_api_identifier, company_sudo.l10n_br_avatax_api_key
        if not api_id or not api_key:
            return {
                "missing_avatax_account": {
                    "message": _("Please create an Avatax account"),
                    "action_text": _("Go to the configuration panel"),
                    "action": self.env.ref('account.action_account_config').with_company(company_sudo)._get_action_dict(),
                    "level": "danger",
                }
            }

        return {}

    def _l10n_br_avatax_check_currency(self):
        if self.currency_id.name != 'BRL':
            return {
                "bad_currency": {
                    "message": _("Brazilian Real is required to calculate taxes with Avatax."),
                    "level": "danger",
                }
            }

        return {}

    @api.model
    def _l10n_br_avatax_check_lines(self, lines, is_service):
        errors = {}

        for line in lines:
            product = line['tempProduct']
            cean = line['itemDescriptor']['cean']
            if not product:
                errors["required_product"] = {
                    "message": _("A product is required on each line when using Avatax."),
                    "level": "danger",
                }
            elif cean and (not cean.isdigit() or not (len(cean) == 8 or 12 <= len(cean) <= 14)):
                errors["bad_cean"] = {
                    "message": _("The barcode of %s must have either 8, or 12 to 14 digits when using Avatax.", product.display_name),
                    "level": "danger",
                }

            if line['lineAmount'] < 0:
                errors["negative_line"] = {
                    "message": _("Avatax Brazil doesn't support negative lines."),
                    "level": "danger",
                }

        if not self._l10n_br_get_non_transport_lines(lines):
            errors["non_transport_line"] = {
                "message": _("Avatax requires at least one non-transport line."),
                "level": "danger",
            }

        service_lines, consumable_lines = partition(
            lambda line: line["tempProduct"].product_tmpl_id._l10n_br_is_only_allowed_on_service_invoice(), lines
        )

        if not is_service:
            if service_lines:
                service_products = self.env["product.product"].union(*[line["tempProduct"] for line in service_lines])
                errors["disallowed_service_products"] = {
                    "message": _(
                        "%(transaction)s is a goods transaction but has service products:\n%(products)s.",
                        transaction=self.display_name,
                        products=service_products.mapped('display_name'),
                    ),
                    "action_text": _("View products"),
                    "action": service_products._get_records_action(name=_("View Product(s)")),
                    "level": "danger",
                }
        else:
            if consumable_lines:
                consumable_products = self.env["product.product"].union(*[line["tempProduct"] for line in consumable_lines])
                errors["disallowed_goods_products"] = {
                    "message": _(
                        "%(transaction)s is a service transaction but has non-service products:\n%(products)s",
                        transaction=self.display_name,
                        products=consumable_products.mapped('display_name'),
                    ),
                    "action_text": _("View products"),
                    "action": consumable_products._get_records_action(name=_("View Product(s)")),
                    "level": "danger",
                }

        return errors

    @api.model
    def _l10n_br_avatax_check_missing_fields_product(self, lines):
        res = {}
        incomplete_products = self.env['product.product']

        for line in lines:
            product = line['tempProduct']
            if product and not product.l10n_br_ncm_code_id:
                incomplete_products |= product

        if incomplete_products:
            res["products_missing_fields_danger"] = {
                    "message": _(
                        "For Brazilian tax calculation you must set a Mercosul NCM Code on the following:\n%(products)s",
                        products=incomplete_products.mapped("display_name")
                    ),
                    "action_text": _("View products"),
                    "action": incomplete_products._l10n_br_avatax_action_missing_fields(self.l10n_br_is_service_transaction),
                    "level": "danger",
                }

        return res

    def _l10n_br_avatax_check_partner(self):
        res = {}
        if self.l10n_br_is_service_transaction:
            partner = self.partner_shipping_id
            city = partner.city_id
            if not city or city.country_id.code != "BR":
                res["missing_city"] = {
                    "message": _("%s must have a city selected in the list of Brazil's cities.", partner.display_name),
                    "action_text": _("View customer"),
                    "action": partner._get_records_action(),
                    "level": "danger",
                }

        return res

    @api.depends(lambda self: self._depends_l10n_br_avatax_warnings())
    def _compute_l10n_br_avatax_warnings(self):
        for record in self:
            if not record.l10n_br_is_avatax:
                record.l10n_br_avatax_warnings = False
                continue

            params = record._get_l10n_br_avatax_service_params()
            lines = self._prepare_l10n_br_avatax_document_lines_service_call(
                params['line_data'],
                params['use_type'],
                params['cnae'],
                params['is_service'],
                params['partner_shipping'],
                params['company'],
            )
            record.l10n_br_avatax_warnings = {
                **record._l10n_br_avatax_check_company(),
                **record._l10n_br_avatax_check_currency(),
                **record._l10n_br_avatax_check_lines(lines, params['is_service']),
                **record._l10n_br_avatax_check_missing_fields_product(lines),
                **record._l10n_br_avatax_check_partner(),
            }

    def _l10n_br_avatax_blocking_errors(self):
        """Only consider 'danger' level errors to be blocking. Other ones are considered warnings."""
        return [error for error in (self.l10n_br_avatax_warnings or {}).values() if error.get('level') == 'danger']

    def _l10n_br_avatax_log(self):
        self.env['account.external.tax.mixin']._enable_external_tax_logging(ICP_LOG_NAME)
        return True

    def _l10n_br_avatax_handle_response(self, service_params, response, title):
        if response.get('error'):
            inner_errors = []
            for error in response['error'].get('innerError', []):
                # Useful inner errors are line-specific. Ones that aren't are typically not useful for the user.
                if 'lineCode' not in error:
                    continue

                product_name = self.env[service_params['line_model_name']].browse(error['lineCode']).product_id.display_name

                inner_errors.append(_('What:'))
                inner_errors.append('- %s: %s' % (product_name, error['message']))

                where = error.get('where', {})
                if where:
                    inner_errors.append(_('Where:'))
                for where_key, where_value in sorted(where.items()):
                    if where_key == 'date':
                        continue
                    inner_errors.append('- %s: %s' % (where_key, where_value))

            return '%s\n%s\n%s' % (title, response['error']['message'], '\n'.join(inner_errors))

        return None

    @api.model
    def _l10n_br_get_non_transport_lines(self, lines):
        return [line for line in lines if not line['tempTransportCostType']]

    @api.model
    def _l10n_br_remove_temp_values_lines(self, lines):
        for line in lines:
            del line['tempTransportCostType']
            del line['tempProduct']

    @api.model
    def _l10n_br_repr_amounts(self, lines):
        """ Ensures all amount fields have the right amount of decimals before sending it to the API. """
        for line in lines:
            for amount_field in ('lineAmount', 'freightAmount', 'insuranceAmount', 'otherCostAmount'):
                line[amount_field] = json_float_round(line[amount_field], AVATAX_PRECISION_DIGITS)

    @api.model
    def _l10n_br_get_partner_type(self, partner):
        if partner.country_code not in ('BR', False):
            return 'foreign'
        elif partner.is_company:
            return 'business'
        else:
            return 'individual'

    @api.model
    def _l10n_br_get_taxes_settings(self, is_service, partner):
        if is_service:
            settings = {
                'cofinsSubjectTo': partner.l10n_br_subject_cofins,
                'pisSubjectTo': partner.l10n_br_subject_pis,
                'csllSubjectTo': 'T' if partner.l10n_br_is_subject_csll else 'E',
            }
            regime = partner.l10n_br_tax_regime
            if regime and regime.startswith('simplified'):
                settings['issRfRateForSimplesTaxRegime'] = partner.l10n_br_iss_simples_rate

            return settings
        else:
            return {'icmsTaxPayer': partner.l10n_br_taxpayer == 'icms'}

    def _get_l10n_br_avatax_service_params(self):
        params = self._get_external_tax_service_params()
        params.update({
            'operation_type': self.l10n_br_goods_operation_type_id,
            'invoice_refs': {},
            'installments': {},
            'id': self.id,
            'model_name': self._name,
            'line_model_name': self._name + '.line',
            'partner': self.partner_id,
            'company': self.company_id,
            'use_type': self.l10n_br_use_type,
            'cnae': self.l10n_br_cnae_code_id,
            'is_service': self.l10n_br_is_service_transaction,
            'is_return': self.l10n_br_goods_operation_type_id.technical_name == 'salesReturn',

            # To be filled by models
            'partner_shipping': None,
            'origin_record': None,
        })
        return params

    @api.model
    def _prepare_l10n_br_avatax_document_line_service_call(self, line_data, record_use_type, cnae, is_service, partner_shipping, company):
        """ Prepares the line data for the /calculations API call. temp* values are here to help with post-processing
        and will be removed before sending by _remove_temp_values_lines.
        """
        # Transform the descriptions of the lines to something Avatax will trim correctly.
        description = line_data['description'] and line_data['description'].replace("\n", " | ")

        base_line = line_data['base_line']
        product = base_line['product_id']
        line = {
            'lineCode': base_line['id'],
            'useType': record_use_type or product.l10n_br_use_type,
            'operationType': line_data['operation_type'].technical_name,
            'otherCostAmount': 0,
            'freightAmount': 0,
            'insuranceAmount': 0,
            'lineTaxedDiscount': base_line['quantity'] * base_line['price_unit'] * (base_line['discount'] / 100.0),
            'lineAmount': base_line['quantity'] * base_line['price_unit'],
            'lineUnitPrice': base_line['price_unit'],
            'numberOfItems': base_line['quantity'],
            'itemDescriptor': {
                'description': description or product.display_name or '',
                'cean': product.barcode or '',
            },
            'tempTransportCostType': product.l10n_br_transport_cost_type,
            'tempProduct': product,
        }

        descriptor = line['itemDescriptor']

        # Sending false or empty string returns errors
        if cnae:
            descriptor['cnae'] = cnae.sanitized_code

        if is_service:
            line['benefitsAbroad'] = partner_shipping.country_id.code != 'BR'
            descriptor['serviceCodeOrigin'] = product.l10n_br_property_service_code_origin_id.code
            descriptor['withLaborAssignment'] = product.l10n_br_labor
            descriptor['hsCode'] = product.l10n_br_ncm_code_id.code or ''

            # Explicitly filter on company, this can be called via controllers which run as superuser and bypass record rules.
            service_codes = product.product_tmpl_id.l10n_br_service_code_ids.filtered(lambda code: code.company_id == company)
            descriptor['serviceCode'] = (
                service_codes.filtered(lambda code: code.city_id == partner_shipping.city_id).code
                or product.l10n_br_property_service_code_origin_id.code
            )
            # Override the CNAE code if the product has a specific one.
            if product.l10n_br_ncm_code_id.l10n_br_cnae_code_id:
                descriptor['cnae'] = product.l10n_br_ncm_code_id.l10n_br_cnae_code_id.sanitized_code
        else:
            descriptor['cest'] = product.l10n_br_cest_code or ''
            descriptor['source'] = product.l10n_br_source_origin or ''
            descriptor['productType'] = product.l10n_br_sped_type or ''
            descriptor['hsCode'] = (product.l10n_br_ncm_code_id.code or '').replace('.', '')
            if product.l10n_br_ncm_code_id.ex:
                descriptor['ex'] = product.l10n_br_ncm_code_id.ex

            uom = base_line['product_uom_id']
            descriptor['unitTaxable'] = uom.name[:6] if uom else ''  # the maximum length allowed by the API is 6
            descriptor['unit'] = uom.name[:6] if uom else ''

        return line

    @api.model
    def _l10n_br_distribute_transport_cost_over_lines(self, lines, transport_cost_type):
        """ Avatax requires transport costs to be specified per line. This distributes transport costs (indicated by
        their product's l10n_br_transport_cost_type) over the lines in proportion to their subtotals. """
        type_to_api_field = {
            'freight': 'freightAmount',
            'insurance': 'insuranceAmount',
            'other': 'otherCostAmount',
        }
        api_field = type_to_api_field[transport_cost_type]

        transport_lines = [line for line in lines if line['tempTransportCostType'] == transport_cost_type]
        regular_lines = self._l10n_br_get_non_transport_lines(lines)
        total = sum(line['lineAmount'] for line in regular_lines)

        if not regular_lines:
            # _compute_l10n_br_avatax_warnings() will inform the user about this
            return []

        for transport_line in transport_lines:
            transport_net = transport_line['lineAmount'] - transport_line['lineTaxedDiscount']
            remaining = transport_net
            for line in regular_lines[:-1]:
                current_cost = float_round(
                    transport_net * (line['lineAmount'] / total),
                    precision_digits=AVATAX_PRECISION_DIGITS
                )
                remaining -= current_cost
                line[api_field] += current_cost

            # put remainder on last line to avoid rounding issues
            regular_lines[-1][api_field] += remaining

        return [line for line in lines if line['tempTransportCostType'] != transport_cost_type]

    @api.model
    def _prepare_l10n_br_avatax_document_lines_service_call(self, line_datas, use_type, cnae, is_service, partner_shipping, company):
        lines = [self._prepare_l10n_br_avatax_document_line_service_call(line_data, use_type, cnae, is_service, partner_shipping, company) for line_data in line_datas]
        lines = self._l10n_br_distribute_transport_cost_over_lines(lines, 'freight')
        lines = self._l10n_br_distribute_transport_cost_over_lines(lines, 'insurance')
        lines = self._l10n_br_distribute_transport_cost_over_lines(lines, 'other')
        return lines

    @api.model
    def _prepare_l10n_br_avatax_document_service_call(self, params):
        """ Returns the full payload containing one record to be used in a /transactions API call. """
        partner = params['partner']
        company_partner = params['company_partner']

        is_service = params['is_service']
        lines = self._prepare_l10n_br_avatax_document_lines_service_call(
            params['line_data'],
            params['use_type'],
            params['cnae'],
            is_service,
            params['partner_shipping'],
            params['company']
        )
        self._l10n_br_remove_temp_values_lines(lines)
        self._l10n_br_repr_amounts(lines)

        partner_shipping_id = params['partner_shipping']
        partner_shipping_location = {}
        if partner_shipping_id != partner:
            partner_shipping_content = {
                'name': partner_shipping_id.display_name,
                'businessName': partner_shipping_id.display_name,
                'type': self._l10n_br_get_partner_type(partner_shipping_id),
                'federalTaxId': partner_shipping_id.vat,
                'cityTaxId': partner_shipping_id.l10n_br_im_code,
                'suframa': partner_shipping_id.l10n_br_isuf_code or '',
                'address': {
                    'number': partner_shipping_id.street_number,
                    'complement': partner_shipping_id.street_number2,
                    'street': partner_shipping_id.street,
                    'neighborhood': partner_shipping_id.street2,
                    'zipcode': partner_shipping_id.zip,
                    'cityName': partner_shipping_id.city,
                    'state': partner_shipping_id.state_id.code,
                    'phone': partner_shipping_id.phone,
                    'email': partner_shipping_id.email
                }
            }
            key = 'rendered' if is_service else 'delivery'
            partner_shipping_location[key] = partner_shipping_content

        taxes_settings_customer = self._l10n_br_get_taxes_settings(is_service, partner)
        taxes_settings_company = self._l10n_br_get_taxes_settings(is_service, company_partner)
        if company_partner.l10n_br_tax_regime == 'simplified':
            taxes_settings_company['pCredSN'] = params['company'].l10n_br_icms_rate

        payments = {}
        if installments := params['installments']:
            payments = {'payment': installments}

        activity_sector = {}
        if params['cnae']:
            activity_sector = {'ActivitySector_CNAE': {'code': params['cnae'].sanitized_code}}

        return {
            'header': {
                'transactionDate': (params['document_date'] or fields.Date.today()).isoformat(),
                'amountCalcType': 'gross',
                'documentCode': '%s_%s' % (params['model_name'], params['id']),
                'messageType': 'services' if is_service else 'goods',
                'companyLocation': '',
                'operationType': params['operation_type'].technical_name,
                **params['invoice_refs'],
                'locations': {
                    'entity': {  # the customer
                        'name': partner.name,
                        'type': self._l10n_br_get_partner_type(partner),
                        'activitySector': {
                            'code': partner.l10n_br_activity_sector,
                        },
                        'taxesSettings': {
                            **taxes_settings_customer,
                        },
                        'taxRegime': partner.l10n_br_tax_regime,
                        'address': {
                            'zipcode': partner.zip,
                            'cityName': partner.city_id.name,
                        },
                        'federalTaxId': partner.vat,
                        'suframa': partner.l10n_br_isuf_code or '',
                    },
                    'establishment': {  # the seller
                        'name': company_partner.name,
                        'type': 'business',
                        'activitySector': {
                            'code': company_partner.l10n_br_activity_sector,
                            **activity_sector,
                        },
                        'taxesSettings': {
                            **taxes_settings_company,
                        },
                        'taxRegime': company_partner.l10n_br_tax_regime,
                        'address': {
                            'zipcode': company_partner.zip,
                            'cityName': company_partner.city_id.name,
                        },
                        'federalTaxId': company_partner.vat,
                        'suframa': company_partner.l10n_br_isuf_code or '',
                    },
                    **partner_shipping_location,
                },
                **payments,
            },
            'lines': lines,
        }

    @api.model
    def _extract_tax_values_from_l10n_br_avatax_detail(self, service_params, line_detail, tax_detail):
        tax_amount = tax_detail['tax']
        if service_params['is_return']:
            tax_amount = -tax_amount

        if tax_detail['taxImpact']['impactOnNetAmount'] == 'Subtracted':
            tax_amount *= -1

        base_amount_currency = line_detail['lineNetFigure']
        # The service API already accounts for the discount in the net figure.
        if not service_params['is_service']:
            base_amount_currency -= line_detail['lineTaxedDiscount']

        return (
            {'name': 'Avalara Brazil', 'company_id': service_params['company'].id},
            {
                'name': tax_detail['taxType'],
                'l10n_br_avatax_code': tax_detail['taxType'],
                'company_id': service_params['company'].id,
                'amount': 1,
                'amount_type': 'percent',
                'price_include_override': 'tax_included' if tax_detail['taxImpact']['impactOnNetAmount'] == 'Included' else 'tax_excluded',
                **({'type_tax_use': self.invoice_filter_type_domain} if 'invoice_filter_type_domain' in self._fields else {})
            },
            {'tax_amount_currency': tax_amount, 'base_amount_currency': base_amount_currency},
        )

    def _l10n_br_call_avatax_taxes(self, company, document_data):
        # To allow saving this response in l10n_br_edi.
        return self.env['account.external.tax.mixin']._l10n_br_iap_calculate_tax(document_data, company)

    def _get_external_taxes(self):
        # EXTENDS 'account.external.tax.mixin'
        res = super()._get_external_taxes()

        br_records = self.filtered(lambda record: record.l10n_br_is_avatax)
        errors = []
        for record in br_records:
            if blocking := record._l10n_br_avatax_blocking_errors():
                errors.append(_(
                    "Taxes cannot be calculated for %(record)s:\n%(errors)s",
                    record=record.display_name, errors="\n".join(f"- {msg['message']}" for msg in blocking)
                ))

        if errors:
            raise ValidationError('\n\n'.join(errors))

        for company, records in br_records.grouped("company_id").items():
            base_line_with_tax_values = []
            for record in records:
                service_params = record._get_l10n_br_avatax_service_params()
                document_data = record._prepare_l10n_br_avatax_document_service_call(service_params)
                base_lines = [data['base_line'] for data in service_params['line_data']]

                api_response = self._l10n_br_call_avatax_taxes(company, document_data)
                error = self._l10n_br_avatax_handle_response(service_params, api_response, _(
                    'Odoo could not fetch the taxes related to %(document)s.',
                    document=record.display_name,
                ))
                if error:
                    errors.append(error)
                    continue

                for base_line, line_results in zip(base_lines, api_response['lines']):
                    tax_values_list = []
                    for tax_detail in line_results['taxDetails']:
                        if tax_detail['taxImpact']['impactOnNetAmount'] != 'Informative' and tax_detail['taxImpact']['accounting'] != 'none':
                            tax_values_list.append(self._extract_tax_values_from_l10n_br_avatax_detail(service_params, line_results, tax_detail))
                    base_line_with_tax_values.append((base_line, tax_values_list))

            if errors:
                raise ValidationError('\n\n'.join(errors))

            res.update(self._process_external_taxes(company, base_line_with_tax_values, 'l10n_br_avatax_code', search_archived_taxes=True))

        return res

    # IAP related methods
    def _l10n_br_iap_request(self, route, company, json=None):
        avatax_api_id, avatax_api_key = company.sudo().l10n_br_avatax_api_identifier, company.sudo().l10n_br_avatax_api_key

        default_endpoint = DEFAULT_IAP_ENDPOINT if company.l10n_br_avalara_environment == 'production' else DEFAULT_IAP_TEST_ENDPOINT
        iap_endpoint = self.env['ir.config_parameter'].sudo().get_param('l10n_br_avatax_iap.endpoint', default_endpoint)
        environment = company.l10n_br_avalara_environment
        url = f'{iap_endpoint}/api/l10n_br_avatax/1/{route}'

        params = {
            'db_uuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid'),
            'account_token': self.env['iap.account'].get(IAP_SERVICE_NAME).sudo().account_token,
            'avatax': {
                'is_production': environment and environment == 'production',
                'json': json or {},
            }
        }

        if avatax_api_id:
            params['api_id'] = avatax_api_id
            params['api_secret'] = avatax_api_key

        start = str(datetime.utcnow())
        response = iap_jsonrpc(url, params=params, timeout=60)  # longer timeout because create_account can take some time
        end = str(datetime.utcnow())

        # Avatax support requested that requests and responses be provided in JSON, so they can easily load them in their
        # internal tools for troubleshooting.
        self._log_external_tax_request(
            'Avatax Brazil',
            ICP_LOG_NAME,
            f"start={start}\n"
            f"end={end}\n"
            f"args={pformat(url)}\n"
            f"request={dumps(json, indent=2)}\n"
            f"response={dumps(response, indent=2)}"
        )

        return response

    def _l10n_br_iap_ping(self, company):
        # This takes company because this function is called directly from res.config.settings instead of a sale.order or account.move
        return self._l10n_br_iap_request('ping', company)

    def _l10n_br_iap_create_account(self, account_data, company):
        # This takes company because this function is called directly from res.config.settings instead of a sale.order or account.move
        return self._l10n_br_iap_request('create_account', company, account_data)

    @api.model
    def _l10n_br_iap_calculate_tax(self, transaction, company):
        return self._l10n_br_iap_request('calculate_tax', company, transaction)
