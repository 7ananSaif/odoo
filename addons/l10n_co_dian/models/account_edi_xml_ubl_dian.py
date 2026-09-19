import logging

from lxml import etree
from hashlib import sha384
from pytz import timezone
from stdnum.co.nit import compact

from collections import defaultdict
from datetime import datetime, timedelta
import re

from odoo import api, models, fields, _
from odoo.addons.account_edi_ubl_cii.models.account_edi_common import FloatFmt
from odoo.addons.account.tools import dict_to_xml
from odoo.addons.l10n_co_dian import xml_utils
from odoo.addons.l10n_co_edi.models.res_partner import FINAL_CONSUMER_VAT
from odoo.addons.l10n_co_edi.models.account_invoice import L10N_CO_EDI_TYPE
from odoo.tools import cleanup_xml_node, frozendict


_logger = logging.getLogger(__name__)


COUNTRIES_ES = {
    "AF": "Afganistán",
    "AX": "Åland",
    "AL": "Albania",
    "DE": "Alemania",
    "AD": "Andorra",
    "AO": "Angola",
    "AI": "Anguila",
    "AQ": "Antártida",
    "AG": "Antigua y Barbuda",
    "SA": "Arabia Saudita",
    "DZ": "Argelia",
    "AR": "Argentina",
    "AM": "Armenia",
    "AW": "Aruba",
    "AU": "Australia",
    "AT": "Austria",
    "AZ": "Azerbaiyán",
    "BS": "Bahamas",
    "BD": "Bangladés",
    "BB": "Barbados",
    "BH": "Baréin",
    "BE": "Bélgica",
    "BZ": "Belice",
    "BJ": "Benín",
    "BM": "Bermudas",
    "BY": "Bielorrusia",
    "BO": "Bolivia",
    "BQ": "Bonaire, San Eustaquio y Saba",
    "BA": "Bosnia y Herzegovina",
    "BW": "Botsuana",
    "BR": "Brasil",
    "BN": "Brunéi",
    "BG": "Bulgaria",
    "BF": "Burkina Faso",
    "BI": "Burundi",
    "BT": "Bután",
    "CV": "Cabo Verde",
    "KH": "Camboya",
    "CM": "Camerún",
    "CA": "Canadá",
    "QA": "Catar",
    "TD": "Chad",
    "CL": "Chile",
    "CN": "China",
    "CY": "Chipre",
    "CO": "Colombia",
    "KM": "Comoras",
    "KP": "Corea del Norte",
    "KR": "Corea del Sur",
    "CI": "Costa de Marfil",
    "CR": "Costa Rica",
    "HR": "Croacia",
    "CU": "Cuba",
    "CW": "Curazao",
    "DK": "Dinamarca",
    "DM": "Dominica",
    "EC": "Ecuador",
    "EG": "Egipto",
    "SV": "El Salvador",
    "AE": "Emiratos Árabes Unidos",
    "ER": "Eritrea",
    "SK": "Eslovaquia",
    "SI": "Eslovenia",
    "ES": "España",
    "US": "Estados Unidos",
    "EE": "Estonia",
    "ET": "Etiopía",
    "PH": "Filipinas",
    "FI": "Finlandia",
    "FJ": "Fiyi",
    "FR": "Francia",
    "GA": "Gabón",
    "GM": "Gambia",
    "GE": "Georgia",
    "GH": "Ghana",
    "GI": "Gibraltar",
    "GD": "Granada",
    "GR": "Grecia",
    "GL": "Groenlandia",
    "GP": "Guadalupe",
    "GU": "Guam",
    "GT": "Guatemala",
    "GF": "Guayana Francesa",
    "GG": "Guernsey",
    "GN": "Guinea",
    "GW": "Guinea-Bisáu",
    "GQ": "Guinea Ecuatorial",
    "GY": "Guyana",
    "HT": "Haití",
    "HN": "Honduras",
    "HK": "Hong Kong",
    "HU": "Hungría",
    "IN": "India",
    "ID": "Indonesia",
    "IQ": "Irak",
    "IR": "Irán",
    "IE": "Irlanda",
    "BV": "Isla Bouvet",
    "IM": "Isla de Man",
    "CX": "Isla de Navidad",
    "IS": "Islandia",
    "KY": "Islas Caimán",
    "CC": "Islas Cocos",
    "CK": "Islas Cook",
    "FO": "Islas Feroe",
    "GS": "Islas Georgias del Sur y Sandwich del Sur",
    "HM": "Islas Heard y McDonald",
    "FK": "Islas Malvinas",
    "MP": "Islas Marianas del Norte",
    "MH": "Islas Marshall",
    "PN": "Islas Pitcairn",
    "SB": "Islas Salomón",
    "TC": "Islas Turcas y Caicos",
    "UM": "Islas ultramarinas de Estados Unidos",
    "VG": "Islas Vírgenes Británicas",
    "VI": "Islas Vírgenes de los Estados Unidos",
    "IL": "Israel",
    "IT": "Italia",
    "JM": "Jamaica",
    "JP": "Japón",
    "JE": "Jersey",
    "JO": "Jordania",
    "KZ": "Kazajistán",
    "KE": "Kenia",
    "KG": "Kirguistán",
    "KI": "Kiribati",
    "XK": "Kosovo",
    "KW": "Kuwait",
    "LA": "Laos",
    "LS": "Lesoto",
    "LV": "Letonia",
    "LB": "Líbano",
    "LR": "Liberia",
    "LY": "Libia",
    "LI": "Liechtenstein",
    "LT": "Lituania",
    "LU": "Luxemburgo",
    "MO": "Macao",
    "MK": "Macedonia",
    "MG": "Madagascar",
    "MY": "Malasia",
    "MW": "Malaui",
    "MV": "Maldivas",
    "ML": "Malí",
    "MT": "Malta",
    "MA": "Marruecos",
    "MQ": "Martinica",
    "MU": "Mauricio",
    "MR": "Mauritania",
    "YT": "Mayotte",
    "MX": "México",
    "FM": "Micronesia",
    "MD": "Moldavia",
    "MC": "Mónaco",
    "MN": "Mongolia",
    "ME": "Montenegro",
    "MS": "Montserrat",
    "MZ": "Mozambique",
    "MM": "Myanmar",
    "NA": "Namibia",
    "NR": "Nauru",
    "NP": "Nepal",
    "NI": "Nicaragua",
    "NE": "Níger",
    "NG": "Nigeria",
    "NU": "Niue",
    "NF": "Norfolk",
    "NO": "Noruega",
    "NC": "Nueva Caledonia",
    "NZ": "Nueva Zelanda",
    "OM": "Omán",
    "NL": "Países Bajos",
    "PK": "Pakistán",
    "PW": "Palaos",
    "PS": "Palestina",
    "PA": "Panamá",
    "PG": "Papúa Nueva Guinea",
    "PY": "Paraguay",
    "PE": "Perú",
    "PF": "Polinesia Francesa",
    "PL": "Polonia",
    "PT": "Portugal",
    "PR": "Puerto Rico",
    "GB": "Reino Unido",
    "EH": "República Árabe Saharaui Democrática",
    "CF": "República Centroafricana",
    "CZ": "República Checa",
    "CG": "República del Congo",
    "CD": "República Democrática del Congo",
    "DO": "República Dominicana",
    "RE": "Reunión",
    "RW": "Ruanda",
    "RO": "Rumania",
    "RU": "Rusia",
    "WS": "Samoa",
    "AS": "Samoa Americana",
    "BL": "San Bartolomé",
    "KN": "San Cristóbal y Nieves",
    "SM": "San Marino",
    "MF": "San Martín",
    "PM": "San Pedro y Miquelón",
    "VC": "San Vicente y las Granadinas",
    "SH": "Santa Elena, Ascensión y Tristán de Acuña",
    "LC": "Santa Lucía",
    "ST": "Santo Tomé y Príncipe",
    "SN": "Senegal",
    "RS": "Serbia",
    "SC": "Seychelles",
    "SL": "Sierra Leona",
    "SG": "Singapur",
    "SX": "Sint Maarten",
    "SY": "Siria",
    "SO": "Somalia",
    "LK": "Sri Lanka",
    "SZ": "Suazilandia",
    "ZA": "Sudáfrica",
    "SD": "Sudán",
    "SS": "Sudán del Sur",
    "SE": "Suecia",
    "CH": "Suiza",
    "SR": "Surinam",
    "SJ": "Svalbard y Jan Mayen",
    "TH": "Tailandia",
    "TW": "Taiwán (República de China)",
    "TZ": "Tanzania",
    "TJ": "Tayikistán",
    "IO": "Territorio Británico del Océano Índico",
    "TF": "Tierras Australes y Antárticas Francesas",
    "TL": "Timor Oriental",
    "TG": "Togo",
    "TK": "Tokelau",
    "TO": "Tonga",
    "TT": "Trinidad y Tobago",
    "TN": "Túnez",
    "TM": "Turkmenistán",
    "TR": "Turquía",
    "TV": "Tuvalu",
    "UA": "Ucrania",
    "UG": "Uganda",
    "UY": "Uruguay",
    "UZ": "Uzbekistán",
    "VU": "Vanuatu",
    "VA": "Vaticano, Ciudad del",
    "VE": "Venezuela",
    "VN": "Vietnam",
    "WF": "Wallis y Futuna",
    "YE": "Yemen",
    "DJ": "Yibuti",
    "ZM": "Zambia",
    "ZW": "Zimbabue",
}


class AccountEdiXmlUbl_Dian(models.AbstractModel):
    """ The technical documentation is available on the dian.gov.co website. Latest version is 1.9:
    https://www.dian.gov.co/impuestos/factura-electronica/Documents/Anexo-Tecnico-Factura-Electronica-de-Venta-vr-1-9.pdf
    """
    _name = 'account.edi.xml.ubl_dian'
    _inherit = ['account.edi.xml.ubl_21']
    _description = "UBL DIAN"

    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------

    def _export_invoice_filename(self, invoice):
        # OVERRIDE account.edi.xml.ubl_21
        return 'dian_%s.xml' % (re.sub(r'[\W_]', '', invoice.name))

    def _export_invoice(self, invoice):
        # EXTENDS account.edi.xml.ubl_21
        xml, errors = super()._export_invoice(invoice)
        if errors:
            return xml, errors
        xml = self._dian_insert_corporate_registration_scheme_node(invoice, xml)
        return self._dian_sign_xml(xml, invoice)

    def _get_document_nsmap(self, vals):
        nsmap = super()._get_document_nsmap(vals)
        nsmap.update({
            'ds': "http://www.w3.org/2000/09/xmldsig#",
            'sts': "dian:gov:co:facturaelectronica:Structures-2-1"
                if vals['document_type'] == 'invoice'
                else "http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures",
            'xades': "http://uri.etsi.org/01903/v1.3.2#",
            'xades141': "http://uri.etsi.org/01903/v1.4.1#",
            'xsi': "http://www.w3.org/2001/XMLSchema-instance",
        })
        return nsmap

    def _add_invoice_config_vals(self, vals):
        super()._add_invoice_config_vals(vals)

        invoice = vals['invoice']

        algorithm = {
            'cude': "CUDE-SHA384",
            'cuds': "CUDS-SHA384",
        }.get(invoice.l10n_co_dian_identifier_type, "CUFE-SHA384")

        prepayments = invoice._l10n_co_dian_get_invoice_prepayments()

        vals.update({
            'document_type': 'debit_note' if invoice.l10n_co_edi_debit_note
                else 'credit_note' if invoice.move_type in ('out_refund', 'in_refund')
                else 'invoice',

            'algorithm': algorithm,
            'prepayments': prepayments,

            # All amounts are reported in company currency (which should be COP)
            # If the invoice is in foreign currency, we just provide the exchange rate in PaymentExchangeRate.
            'use_company_currency': True,

            # Fixed tax (e.g. IBUA) amounts should be accounted not as AllowanceCharges but as taxes
            'fixed_taxes_as_allowance_charges': False,
        })

    def _add_invoice_base_lines_vals(self, vals):
        # EXTEND account.edi.xml.ubl_21
        super()._add_invoice_base_lines_vals(vals)
        for base_line in vals['base_lines']:
            self._transform_iva_withholding_base_amount(base_line)

    def _transform_iva_withholding_base_amount(self, base_line):
        # Taxes with type '05' are retention taxes (15 %) that apply on the *tax amount* of a regular VAT tax
        # Hence, the tax "15% RteVAT 19%" is encoded as a -2.85% tax in Odoo

        # We now transform those taxes back to have their proper base amounts.
        # On invoice line, look at the sibling tax detail '01' and extract its exact tax amount.

        # see constraint DSAY05: the Taxable Amount for the taxes with type '05' should be equal to
        # the Tax Amount on which the taxes with type '01' were applied

        def get_tax_data(l10n_co_edi_type_code):
            return next(
                (
                    tax_data
                    for tax_data in base_line['tax_details']['taxes_data']
                    if tax_data['tax'].l10n_co_edi_type.code == l10n_co_edi_type_code
                ),
                None,
            )

        tax_data_05 = get_tax_data('05')
        if tax_data_05:
            tax_data_01 = get_tax_data('01')
            tax_data_05['base_amount'] = tax_data_01['tax_amount'] if tax_data_01 else 0.0

    def _add_invoice_tax_grouping_function_vals(self, vals):
        invoice = vals['invoice']
        self._add_document_tax_grouping_function_vals(vals)

        total_grouping_function = vals['total_grouping_function']
        tax_grouping_function = vals['tax_grouping_function']

        # For support document, only the taxes IVA (01), ReteICA (05), ReteRenta (06) should be included
        def total_grouping_function_excluding_support_document(base_line, tax_data):
            tax = tax_data and tax_data['tax']
            if invoice.l10n_co_edi_is_support_document and tax and tax.l10n_co_edi_type.code not in {'01', '05', '06'}:
                return None
            return total_grouping_function(base_line, tax_data)

        def tax_grouping_function_excluding_support_document(base_line, tax_data):
            tax = tax_data and tax_data['tax']
            if invoice.l10n_co_edi_is_support_document and tax and tax.l10n_co_edi_type.code not in {'01', '05', '06'}:
                return None
            return tax_grouping_function(base_line, tax_data)

        vals['total_grouping_function'] = total_grouping_function_excluding_support_document
        vals['tax_grouping_function'] = tax_grouping_function_excluding_support_document

    def _add_document_tax_grouping_function_vals(self, vals):
        def total_grouping_function(base_line, tax_data):
            if tax_data and tax_data['tax'].l10n_co_edi_type.retention:
                return None
            return True

        def tax_grouping_function(base_line, tax_data):
            """ Group the taxes by colombian type using the (tax.amount, tax.amount_type, tax.l10n_co_edi_type) """
            tax = tax_data and tax_data['tax']

            if not tax:
                return None

            if tax.l10n_co_edi_type.code == '32':
                # ICL (tax on alcoholic beverages) is a tax based on the alcohol percentage in the bottle.
                # It is always sent in LTRs according to the specifications listed in the DIAN documentation.
                amount = tax.amount / base_line['product_id'].l10n_co_edi_ref_nominal_tax * base_line['quantity']
            elif tax.l10n_co_edi_type.code == '34':
                # IBUA (tax on sugar beverages) is a tax based on the quantity of sugar per 100mL
                # e.g. if the quantity of sugar per 100mL is > 10gr -> tax of 35$ per 100mL
                # In Odoo, we use fixed taxes and a field for the volume of the product: l10n_co_edi_ref_nominal_tax
                # Hence, we can infer the rate per 100mL of the tax
                amount = tax.amount * 100 / base_line['product_id'].l10n_co_edi_ref_nominal_tax
            elif tax.l10n_co_edi_type.code == '05':
                # Taxes with type '05' are retention taxes (15 %) that apply on the *tax amount* of a regular VAT tax
                # Hence, the tax "15% RteVAT 19%" is encoded as a -2.85% tax in Odoo. However, in the UBL, it should appear as 15%.
                # Thus, we find the percentage of the IVA tax on the same line, and divide by it.
                if iva_tax := next(
                    (
                        tax_data['tax']
                        for tax_data in base_line['tax_details']['taxes_data']
                        if tax_data['tax'].l10n_co_edi_type.code == '01'
                    ),
                    None,
                ):
                    amount = tax.amount * 100 / iva_tax.amount
            else:
                amount = tax.amount

            return {
                'l10n_co_edi_type': tax.l10n_co_edi_type,
                'amount_type': tax.amount_type,
                'amount': amount,
                'is_withholding_tax': tax.l10n_co_edi_type.retention,
            }

        vals['total_grouping_function'] = total_grouping_function
        vals['tax_grouping_function'] = tax_grouping_function

    # -------------------------------------------------------------------------
    # EXPORT: Helpers
    # -------------------------------------------------------------------------

    def _get_cufe_cude_cuds(self, document_node, vals):
        """ Returns the values used to compute the CUFE/CUDE/CUDS """
        invoice = vals['invoice']
        operation_mode = self._dian_get_operation_mode(invoice)

        def format_float(amount, precision_digits=vals['currency_dp']):
            return self.format_float(amount, precision_digits)

        def get_tax_amount(l10n_co_edi_type_code):
            """ Get the tax amount associated with a given colombian tax type code. """
            def grouping_function(base_line, tax_data):
                return tax_data and tax_data['tax'].l10n_co_edi_type.code == l10n_co_edi_type_code

            base_lines_aggregated_tax_details = self.env['account.tax']._aggregate_base_lines_tax_details(
                vals['base_lines'],
                grouping_function
            )
            aggregated_tax_details = self.env['account.tax']._aggregate_base_lines_aggregated_values(
                base_lines_aggregated_tax_details
            )
            if True in aggregated_tax_details:
                return aggregated_tax_details[True]['tax_amount']
            return 0.0

        if invoice.l10n_co_dian_identifier_type in ('cude', 'cuds'):
            key = operation_mode.dian_software_security_code
        else:
            key = invoice.journal_id.l10n_co_dian_technical_key

        monetary_total_tag = 'cac:LegalMonetaryTotal' if vals['document_type'] in {'invoice', 'credit_note'} else 'cac:RequestedMonetaryTotal'

        cufe_cude_cuds_vals = {
            'invoice_id': document_node['cbc:ID']['_text'],
            'issue_date': document_node['cbc:IssueDate']['_text'],
            'issue_time': document_node['cbc:IssueTime']['_text'],  # invoice time (including tz)
            'line_extension_amount': document_node[monetary_total_tag]['cbc:LineExtensionAmount']['_text'],
            'tax_code_01': '01',
            'ValImp1': format_float(get_tax_amount('01')),
            'tax_code_04': '04',
            'ValImp2': format_float(get_tax_amount('04')),
            'tax_code_03': '03',
            'ValImp3': format_float(get_tax_amount('03')),
            'ValTotFac': document_node[monetary_total_tag]['cbc:PayableAmount']['_text'],
            'supplier_company_id': vals['supplier']._get_vat_without_verification_code(),
            'customer_company_id': vals['customer']._get_vat_without_verification_code(),
            'key': key or 'missing_key',
            'profile_execution_id': document_node['cbc:ProfileExecutionID']['_text'],
        }
        if invoice.l10n_co_edi_is_support_document:
            [cufe_cude_cuds_vals.pop(k) for k in ('tax_code_04', 'ValImp2', 'tax_code_03', 'ValImp3')]

        return "".join(str(res) for res in cufe_cude_cuds_vals.values())

    # -------------------------------------------------------------------------
    # EXPORT: Templates for invoice header nodes
    # -------------------------------------------------------------------------

    def _get_invoice_node(self, vals):
        document_node = super()._get_invoice_node(vals)
        self._fill_cufe_cude_cuds(document_node, vals)
        return document_node

    def _add_invoice_header_nodes(self, document_node, vals):
        super()._add_invoice_header_nodes(document_node, vals)

        invoice = vals['invoice']
        line_count_numeric = len([base_line for base_line in vals['base_lines'] if not base_line['special_mode']])

        document_node.update({
            'xsi:schemaLocation': {
                'invoice': "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2     "
                    "http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-Invoice-2.1.xsd",
                'credit_note': "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2    "
                    "http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-CreditNote-2.1.xsd",
                'debit_note': "urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2    "
                    "http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-DebitNote-2.1.xsd"
            }[vals['document_type']],
            'cbc:UBLVersionID': {'_text': 'UBL 2.1'},
            'cbc:CustomizationID': {'_text': self._dian_get_customization_id(invoice)},
            'cbc:ProfileID': {'_text': invoice._l10n_co_edi_get_electronic_invoice_type_info()},
            'cbc:ProfileExecutionID': {'_text': '2' if invoice.company_id.l10n_co_dian_test_environment else '1'},
            'cbc:UUID': {
                'schemeID': '2' if invoice.company_id.l10n_co_dian_test_environment else '1',
                'schemeName': vals['algorithm'],
            },
            'cbc:IssueDate': {'_text': invoice.l10n_co_dian_post_time.date().isoformat()},
            'cbc:IssueTime': {'_text': invoice.l10n_co_dian_post_time.strftime("%H:%M:%S-05:00")},
            'cbc:InvoiceTypeCode': {'_text': self._dian_get_document_type_code(invoice)} if vals['document_type'] == 'invoice' else None,
            'cbc:CreditNoteTypeCode': {'_text': self._dian_get_document_type_code(invoice)} if vals['document_type'] == 'credit_note' else None,
            'cbc:Note': None,
            'cbc:DocumentCurrencyCode': {
                '_text': "COP",
                'listAgencyID': "6",
                'listAgencyName': "United Nations Economic Commission for Europe",
                'listID': "ISO 4217 Alpha",
            },
            'cbc:LineCountNumeric': {'_text': line_count_numeric},
            'cac:InvoicePeriod': {
                'cbc:StartDate': {'_text': invoice.invoice_date},
                'cbc:EndDate': {'_text': invoice.invoice_date},
            } if invoice.l10n_co_edi_operation_type in ['22', '32'] else None,
            'cac:DiscrepancyResponse': (
                {
                    'cbc:ReferenceID': {'_text': invoice.reversed_entry_id.name},
                    'cbc:ResponseCode': {'_text': invoice.l10n_co_edi_description_code_credit},
                    'cbc:Description': {'_text': dict(invoice._fields['l10n_co_edi_description_code_credit'].selection).get(invoice.l10n_co_edi_description_code_credit)}
                }
                if invoice.l10n_co_edi_operation_type == '20' or invoice.move_type == 'in_refund'
                else {
                    'cbc:ReferenceID': {'_text': invoice.debit_origin_id.name},
                    'cbc:ResponseCode': {'_text': invoice.l10n_co_edi_description_code_debit},
                    'cbc:Description': {'_text': dict(invoice._fields['l10n_co_edi_description_code_debit'].selection).get(invoice.l10n_co_edi_description_code_debit)}
                }
                if invoice.l10n_co_edi_operation_type == '30'
                else None
            ),
        })

        document_node['cac:OrderReference']['cbc:SalesOrderID'] = None

        document_node['cac:BillingReference'] = self._get_billing_reference_node(invoice)

        document_node.update({
            'cac:PrepaidPayment': [
                {
                    'cbc:ID': {'_text': p['name']},
                    'cbc:PaidAmount': {
                        '_text': self.format_float(p['amount'], invoice.company_currency_id.decimal_places),
                        'currencyID': invoice.company_currency_id.name
                    },
                    'cbc:ReceivedDate': {'_text': p['date']},
                }
                for p in vals['prepayments']
            ] if vals['document_type'] in {'invoice', 'credit_note'} else None,
        })

    def _add_invoice_accounting_supplier_party_nodes(self, document_node, vals):
        super()._add_invoice_accounting_supplier_party_nodes(document_node, vals)
        document_node['cac:AccountingSupplierParty']['cbc:AdditionalAccountID'] = {
            '_text': vals['supplier']._l10n_co_edi_get_partner_type()
        }

    def _add_invoice_accounting_customer_party_nodes(self, document_node, vals):
        super()._add_invoice_accounting_customer_party_nodes(document_node, vals)
        document_node['cac:AccountingCustomerParty']['cbc:AdditionalAccountID'] = {
            '_text': vals['customer'].commercial_partner_id._l10n_co_edi_get_partner_type()
        }

    def _add_invoice_delivery_nodes(self, document_node, vals):
        pass

    def _add_invoice_payment_means_nodes(self, document_node, vals):
        # OVERRIDE account.edi.xml.ubl_21
        invoice = vals['invoice']
        document_node['cac:PaymentMeans'] = {
            'cbc:ID': {'_text': '1' if invoice.l10n_co_edi_is_direct_payment else '2'},
            'cbc:PaymentMeansCode': {'_text': invoice.l10n_co_edi_payment_option_id.code},
            'cbc:PaymentDueDate': {'_text': invoice.invoice_date_due},
            'cbc:PaymentID': {'_text': invoice.payment_reference or invoice.name},
        }

    def _fill_cufe_cude_cuds(self, document_node, vals):
        invoice = vals['invoice']
        # Add CUFE/CUDE/CUDS
        cufe_cude_cuds = self._get_cufe_cude_cuds(document_node, vals)
        document_node['cbc:UUID']['_text'] = sha384(cufe_cude_cuds.encode()).hexdigest()  # as stated in the "Anexo Tecnico" file, SHA384 must be used
        document_node['cbc:Note'] = [
            document_node['cbc:Note'],
            {'_text': cufe_cude_cuds}
        ]

        if invoice.currency_id.name != "COP":
            document_node['cac:PaymentExchangeRate'] = {
                'cbc:SourceCurrencyCode': {'_text': "COP"},
                'cbc:SourceCurrencyBaseRate': {'_text': (rate := self.format_float(1 / invoice.invoice_currency_rate, 6))},
                'cbc:TargetCurrencyCode': {'_text': invoice.currency_id.name},
                'cbc:TargetCurrencyBaseRate': {'_text': "1.00"},
                'cbc:CalculationRate': {'_text': rate},
                'cbc:Date': {'_text': invoice.invoice_date},
            }

    def _get_address_node(self, vals):
        partner = vals['partner']
        return {
            'cbc:ID': {'_text': str(partner.city_id.l10n_co_edi_code).zfill(5)},  # Codigo Municipio
            'cbc:CityName': {'_text': partner.city},
            'cbc:PostalZone': {'_text': partner.zip},
            'cbc:CountrySubentity': {'_text': partner.state_id.name},
            'cbc:CountrySubentityCode': {'_text': str(partner.state_id.l10n_co_edi_code).zfill(2)},
            'cac:AddressLine': {
                'cbc:Line': {'_text': partner._l10n_co_edi_get_company_address()}
            },
            'cac:Country': {
                'cbc:IdentificationCode': {'_text': partner.country_id.code},
                'cbc:Name': {
                    '_text': COUNTRIES_ES.get(partner.country_code) if vals.get('use_es_country_name') else partner.country_id.name,
                    'languageID': 'es' if partner.country_code == 'CO' else 'en',
                },
            },
        }

    def _get_party_node(self, vals):
        partner = vals['partner']
        invoice = vals['invoice']
        role = vals['role']
        commercial_partner = partner.commercial_partner_id

        return {
            'cbc:IndustryClassificationCode': {
                '_text': invoice.company_id.l10n_co_edi_header_actividad_economica
            } if role == 'supplier' and invoice.l10n_co_dian_identifier_type != 'cuds' else None,
            'cac:PartyIdentification': {
                'cbc:ID': {
                    '_text': commercial_partner._get_vat_without_verification_code(),
                    'schemeName': (partner_code := commercial_partner._l10n_co_edi_get_carvajal_code_for_identification_type()),
                    # every Colombian NIT (code='rut') comprises a validation digit, it is mandatory to add it here
                    'schemeID': commercial_partner._get_vat_verification_code() if partner_code == '31' else None,
                }
            } if not commercial_partner.is_company else None,
            'cac:PartyName': {
                'cbc:Name': {
                    '_text': partner.display_name
                }
            },
            'cac:PhysicalLocation': {
                'cac:Address': self._get_address_node({'partner': partner, 'use_es_country_name': True})
            } if partner.vat != FINAL_CONSUMER_VAT else None,
            'cac:PartyTaxScheme': {
                'cbc:RegistrationName': {
                    '_text': commercial_partner.name
                },
                'cbc:CompanyID': {
                    '_text': commercial_partner._get_vat_without_verification_code(),
                    'schemeName': commercial_partner._l10n_co_edi_get_carvajal_code_for_identification_type(),
                    'schemeAgencyName': "CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)",
                    'schemeAgencyID': "195",
                    'schemeID': commercial_partner._get_vat_verification_code()
                    if partner._l10n_co_edi_get_carvajal_code_for_identification_type() == '31' else None,
                },
                'cbc:TaxLevelCode': {
                    '_text': ';'.join(commercial_partner.l10n_co_edi_obligation_type_ids.mapped('name'))
                },
                # 'Consumidor Final' is used in B2C, hence no address should be filled
                'cac:RegistrationAddress': self._get_address_node({'partner': commercial_partner}) if commercial_partner.vat != FINAL_CONSUMER_VAT else None,
                'cac:TaxScheme': {
                    'cbc:ID': {
                        '_text': commercial_partner._l10n_co_edi_get_fiscal_regimen_code()
                    },
                    'cbc:Name': {
                        '_text': 'No aplica' if (name := commercial_partner._l10n_co_edi_get_fiscal_regimen_name()) == 'No Aplica' else name
                    }
                },
            },
            'cac:PartyLegalEntity': {
                'cbc:RegistrationName': {
                    '_text': commercial_partner.name
                },
                'cbc:CompanyID': {
                    '_text': commercial_partner._get_vat_without_verification_code(),
                    'schemeName': commercial_partner._l10n_co_edi_get_carvajal_code_for_identification_type(),
                    'schemeAgencyName': "CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)",
                    'schemeAgencyID': "195",
                    'schemeID': commercial_partner._get_vat_verification_code(),
                },
            } if partner.vat != FINAL_CONSUMER_VAT else None,
            'cac:Contact': {
                'cbc:Name': {
                    '_text': partner.name
                },
                'cbc:Telephone': {
                    '_text': partner.phone
                },
                'cbc:ElectronicMail': {
                    '_text': partner.email
                },
            } if partner.vat != FINAL_CONSUMER_VAT else None,
        }

    def _get_billing_reference_node(self, invoice):
        """Get the BillingReference node for credit/debit notes."""
        reference_invoice = None
        if invoice.l10n_co_edi_operation_type == '20' or invoice.move_type == 'in_refund':
            reference_invoice = invoice.reversed_entry_id
            scheme_name = "CUDS" if invoice.move_type == 'in_refund' else "CUFE"
        elif invoice.l10n_co_edi_operation_type == '30':
            reference_invoice = invoice.debit_origin_id
            scheme_name = "CUFE"

        if reference_invoice:
            return {
                'cac:InvoiceDocumentReference': {
                    'cbc:ID': {'_text': reference_invoice.name},
                    'cbc:UUID': {
                        '_text': reference_invoice.l10n_co_edi_cufe_cude_ref,
                        'schemeName': f"{scheme_name}-SHA384"
                    },
                    'cbc:IssueDate': {'_text': reference_invoice.invoice_date.isoformat()},
                }
            }
        return None

    # -------------------------------------------------------------------------
    # EXPORT: Templates for invoice amount nodes
    # -------------------------------------------------------------------------

    def _add_document_tax_total_nodes(self, document_node, vals):
        # We need multiple tax total nodes, one per l10n_co_edi_type.

        base_lines_aggregated_tax_details = {}
        aggregated_tax_details = {}
        base_unit_measure_by_grouping_key = defaultdict(float)

        def grouping_function(base_line, tax_data):
            grouping_key = vals['tax_grouping_function'](base_line, tax_data)
            if grouping_key is not None and tax_data['tax'].l10n_co_edi_type.code in ['22', '32', '34']:
                # Handle INC Bolsas/ICL/IBUA taxes
                if tax_data['tax'].l10n_co_edi_type.code == '22':
                    base_unit_measure_by_grouping_key[frozendict(grouping_key)] = tax_data['tax'].amount
                else:
                    base_unit_measure_by_grouping_key[frozendict(grouping_key)] += (
                        base_line['product_id'].l10n_co_edi_ref_nominal_tax *
                        (base_line['quantity'] if tax_data['tax'].l10n_co_edi_type.code == '34' else 1)
                    )
            return grouping_key

        base_lines_aggregated_tax_details = self.env['account.tax']._aggregate_base_lines_tax_details(
            vals['base_lines'],
            grouping_function,
        )
        aggregated_tax_details = self.env['account.tax']._aggregate_base_lines_aggregated_values(
            base_lines_aggregated_tax_details,
        )

        grouped_aggregated_tax_details_by_l10n_co_edi_type = {'tax': defaultdict(dict), 'withholding_tax': defaultdict(dict)}

        for grouping_key, values in aggregated_tax_details.items():
            if grouping_key:
                l10n_co_edi_type = grouping_key['l10n_co_edi_type']
                key = 'withholding_tax' if grouping_key['is_withholding_tax'] else 'tax'
                grouped_aggregated_tax_details_by_l10n_co_edi_type[key][l10n_co_edi_type][grouping_key] = values
                values['base_unit_measure'] = base_unit_measure_by_grouping_key[grouping_key]

        document_node['cac:TaxTotal'] = [
            self._get_tax_total_node({**vals, 'aggregated_tax_details': tax_details, 'role': 'document'})
            for tax_details in grouped_aggregated_tax_details_by_l10n_co_edi_type['tax'].values()
        ]
        if vals['document_type'] == 'invoice':
            document_node['cac:WithholdingTaxTotal'] = [
                self._get_tax_total_node({**vals, 'aggregated_tax_details': tax_details, 'role': 'document', 'sign': -1})
                for tax_details in grouped_aggregated_tax_details_by_l10n_co_edi_type['withholding_tax'].values()
            ]

    def _add_invoice_monetary_total_nodes(self, document_node, vals):
        """ The validator will check that:
        * LineExtensionAmount = sum(InvoiceLine/LineExtensionAmount)
        * TaxExclusiveAmount = sum(InvoiceLine/TaxTotal/TaxSubtotal/TaxableAmount)
        * TaxInclusiveAmount = LineExtensionAmount + sum(Invoice/TaxTotal/TaxAmount)
        * ChargeTotalAmount = sum(Invoice/AllowanceCharge[ChargeIndicator='true'] [1]
        * AllowanceTotalAmount = sum(Invoice/AllowanceCharge[ChargeIndicator='false'] [1]
        * PrepaidAmount = sum(Invoice/PrepaidPayment/PaidAmount)
        * PayableAmount = TaxInclusiveAmount - AllowanceTotalAmount + ChargeTotalAmount [2]

        [1]: Will always be 0
        [2]: PrepaidAmount is not used in the PayableAmount
        [3]: Withholdings have no impact in any of these subtotals, they are optionals
        """
        # The monetary total should not take into account withholding taxes.
        super()._add_invoice_monetary_total_nodes(document_node, vals)

        prepaid_amount = sum(p['amount'] for p in vals['prepayments'])

        monetary_total_tag = self._get_tags_for_document_type(vals)['monetary_total']

        document_node[monetary_total_tag].update({
            'cbc:PrepaidAmount': {
                '_text': self.format_float(prepaid_amount, vals['currency_dp']),
                'currencyID': vals['currency_name'],
            } if prepaid_amount else None,
            'cbc:PayableAmount': {
                '_text': document_node[monetary_total_tag]['cbc:TaxInclusiveAmount']['_text'],
                'currencyID': vals['currency_name'],
            },
        })

    # -------------------------------------------------------------------------
    # EXPORT: Templates for tax-related nodes
    # -------------------------------------------------------------------------

    def _get_tax_subtotal_node(self, vals):
        tax_details = vals['tax_details']
        grouping_key = vals['grouping_key']

        if grouping_key['l10n_co_edi_type'].code not in ['22', '32', '34']:
            tax_subtotal_node = super()._get_tax_subtotal_node(vals)
            tax_subtotal_node['cbc:Percent'] = None
        else:
            # Special subtotals for INC Bolsas/ICL/IBUA taxes
            tax_subtotal_node = {
                'cbc:TaxAmount': {
                    '_text': self.format_float(tax_details['tax_amount'], vals['currency_dp']),
                    'currencyID': vals['currency_name'],
                },
                'cbc:BaseUnitMeasure': {
                    '_text': tax_details['base_unit_measure'],
                    'unitCode': {
                        '22': 'NIU',
                        '32': 'LTR',
                        '34': 'ML'
                    }.get(grouping_key['l10n_co_edi_type'].code),
                },
                'cbc:PerUnitAmount': {
                    '_text': self.format_float(grouping_key['amount'], 2),
                    'currencyID': vals['currency_name']
                },
                'cac:TaxCategory': self._get_tax_category_node(vals),
            }

        return tax_subtotal_node

    def _get_tax_category_node(self, vals):
        grouping_key = vals['grouping_key']
        return {
            # DIAN accepts up to 3 decimals for this node. But it also checks that the type of tax is consistent with the tax amount reported.
            # For instance: '19.00' for an 'IVA' tax is allowed, but '19.000' is not
            # (it raises: "FAS01b, Rechazo: Tributo IVA (01), INC (04) informado no coincide, revisar Porcentaje, Nombre y ID.").
            # The majority of taxes have only 2 decimals, but some have 3 (and they should be reported with all their decimals).
            'cbc:Percent': {
                '_text': FloatFmt(abs(grouping_key['amount']), 2, 3)  # withholding taxes are reported as positives
            } if grouping_key['l10n_co_edi_type'].code not in {'22', '32', '34'}
            else None,  # Don't include Percent for INC Bolsas/ICL/IBUA taxes
            'cac:TaxScheme': {
                'cbc:ID': {
                    '_text': grouping_key['l10n_co_edi_type'].code,
                },
                'cbc:Name': {
                    '_text': 'No aplica' if grouping_key['l10n_co_edi_type'].name == 'No Aplica' else grouping_key['l10n_co_edi_type'].name
                },
            }
        }

    # -------------------------------------------------------------------------
    # EXPORT: Templates for invoice line nodes
    # -------------------------------------------------------------------------

    def _add_document_line_amount_nodes(self, line_node, vals):
        super()._add_document_line_amount_nodes(line_node, vals)
        base_line = vals['base_line']

        # Colombia follows a standard that very much resembles the UNSPSC
        uom = base_line['product_uom_id'].l10n_co_edi_ubl or '94'
        quantity_tag = self._get_tags_for_document_type(vals)['line_quantity']
        line_node[quantity_tag]['unitCode'] = uom

    def _add_invoice_line_note_nodes(self, line_node, vals):
        invoice = vals['invoice']
        base_line = vals['base_line']
        if invoice.l10n_co_edi_operation_type == '09' and base_line['product_id']:
            line_node['cbc:Note'] = {'_text': f"Contrato de servicios AIU por Concepto de: {base_line['product_id'].name}"}

    def _add_invoice_line_period_nodes(self, line_node, vals):
        super()._add_invoice_line_period_nodes(line_node, vals)

        line = vals['base_line']['record']
        # Support documents have a special InvoicePeriod node
        if line.move_id.l10n_co_edi_is_support_document:
            line_node['cac:InvoicePeriod'] = {
                'cbc:StartDate': {'_text': line.move_id.invoice_date},
                'cbc:DescriptionCode': {'_text': 1},
                'cbc:Description': {'_text': 'Por operación'},
            }

    def _add_document_line_tax_total_nodes(self, line_node, vals):
        # Colombian particularity: there should be one `TaxTotal` per colombian tax type, comprising 1 or more
        # `TaxSubtotal` (1 per tax amount). The same applies for `WithholdingTaxTotal`.
        base_unit_measure_by_grouping_key = defaultdict(float)

        def grouping_function(base_line, tax_data):
            grouping_key = vals['tax_grouping_function'](base_line, tax_data)
            if grouping_key is not None and tax_data['tax'].l10n_co_edi_type.code in ['22', '32', '34']:
                # - INC Bolsas (tax on plastic bags) is a tax based on the number of plastic bags used in the sale.
                #   It is always sent in NIUs (Number of Items) according to the specifications listed in the DIAN documentation.
                # - ICL (tax on alcoholic beverages) is a tax based on the alcohol percentage in the bottle.
                #   It is always sent in LTRs according to the specifications listed in the DIAN documentation.
                # - IBUA (tax on sugar beverages) is a tax based on the quantity of sugar per 100mL
                #   e.g. if the quantity of sugar per 100mL is > 10gr -> tax of 35$ per 100mL
                # In Odoo, we have a field for the volume of the product : l10n_co_edi_ref_nominal_tax
                if tax_data['tax'].l10n_co_edi_type.code == '22':
                    base_unit_measure_by_grouping_key[frozendict(grouping_key)] = tax_data['tax'].amount
                else:
                    base_unit_measure_by_grouping_key[frozendict(grouping_key)] += (
                        base_line['product_id'].l10n_co_edi_ref_nominal_tax *
                        (base_line['quantity'] if tax_data['tax'].l10n_co_edi_type.code == '34' else 1)
                    )
            return grouping_key

        aggregated_tax_details = self.env['account.tax']._aggregate_base_line_tax_details(
            vals['base_line'],
            grouping_function,
        )

        grouped_aggregated_tax_details_by_l10n_co_edi_type = {'tax': defaultdict(dict), 'withholding_tax': defaultdict(dict)}

        for grouping_key, values in aggregated_tax_details.items():
            if grouping_key:
                l10n_co_edi_type = grouping_key['l10n_co_edi_type']
                key = 'withholding_tax' if grouping_key['is_withholding_tax'] else 'tax'
                grouped_aggregated_tax_details_by_l10n_co_edi_type[key][l10n_co_edi_type][grouping_key] = values
                values['base_unit_measure'] = base_unit_measure_by_grouping_key[grouping_key]

        line_node['cac:TaxTotal'] = [
            self._get_tax_total_node({**vals, 'aggregated_tax_details': tax_details, 'role': 'line'})
            for tax_details in grouped_aggregated_tax_details_by_l10n_co_edi_type['tax'].values()
        ]
        if vals['document_type'] == 'invoice':
            line_node['cac:WithholdingTaxTotal'] = [
                self._get_tax_total_node({**vals, 'aggregated_tax_details': tax_details, 'role': 'line', 'sign': -1})
                for tax_details in grouped_aggregated_tax_details_by_l10n_co_edi_type['withholding_tax'].values()
            ]

    def _add_invoice_line_item_nodes(self, line_node, vals):
        super()._add_invoice_line_item_nodes(line_node, vals)

        base_line = vals['base_line']
        line = base_line['record']
        invoice = vals['invoice']
        product = base_line['product_id']
        if line.move_id.l10n_co_edi_type == L10N_CO_EDI_TYPE['Export Invoice']:
            line_node['cac:Item']['cbc:BrandName'] = {'_text': product.l10n_co_edi_brand}
            line_node['cac:Item']['cbc:ModelName'] = {'_text': product.l10n_co_edi_customs_code}

        l10n_co_product_code, product_code_scheme_id, product_code_scheme_name = line._l10n_co_edi_get_product_code()
        line_node['cac:Item']['cac:SellersItemIdentification'] = {
            'cbc:ID': {'_text': product.code if not invoice.l10n_co_edi_is_support_document else l10n_co_product_code},
            'cbc:ExtendedID': {'_text': l10n_co_product_code} if invoice.l10n_co_edi_is_support_document else None,
        }
        line_node['cac:Item']['cac:StandardItemIdentification'] = {
            'cbc:ID': {
                '_text': l10n_co_product_code,
                'schemeID': product_code_scheme_id,
                'schemeName': product_code_scheme_name,
            }
        }

    def _add_document_line_tax_category_nodes(self, line_node, vals):
        # No InvoiceLine/Item/ClassifiedTaxCategory in Colombia
        pass

    def _get_line_fixed_tax_allowance_charge_nodes(self, vals):
        # Fixed taxes (e.g. the IBUA sugar tax) should not be reported as AllowanceCharges.
        return []

    def _get_line_discount_allowance_charge_node(self, vals):
        discount_node = super()._get_line_discount_allowance_charge_node(vals)
        if discount_node:
            discount_node['cbc:AllowanceChargeReasonCode'] = {'_text': '00'}  # unconditional discount
            discount_node['cbc:MultiplierFactorNumeric'] = {'_text': vals['base_line']['discount']}
            discount_node['cbc:BaseAmount'] = {
                '_text': self.format_float(vals['gross_subtotal'], vals['currency_dp']),
                'currencyID': vals['currency_name'],
            }
        return discount_node

    def _add_document_line_price_nodes(self, line_node, vals):
        super()._add_document_line_price_nodes(line_node, vals)
        base_line = vals['base_line']
        # Colombia follows a standard that very much resembles the UNSPSC
        uom = base_line['product_uom_id'].l10n_co_edi_ubl or '94'
        line_node['cac:Price']['cbc:BaseQuantity'] = {
            '_text': base_line['quantity'],
            'unitCode': uom,
        }

    # -------------------------------------------------------------------------
    # EXPORT: Constraints
    # -------------------------------------------------------------------------

    def _export_invoice_constraints(self, move, vals):
        # EXTENDS account.edi.xml.ubl_21
        constraints = super()._export_invoice_constraints(move, vals)
        now = fields.Datetime.now()
        oldest_date = now - timedelta(days=5)
        newest_date = now + timedelta(days=10)
        if not (oldest_date <= fields.Datetime.to_datetime(move.invoice_date) <= newest_date):
            constraints['dian_date'] = _("The issue date can not be older than 5 days or more than 5 days in the future.")
        # required fields on invoice
        if not move.l10n_co_dian_post_time:
            constraints['l10n_co_dian_post_time'] = _("A posted time is required to compute the CUFE/CUDE/CUDS.")
        if not move.l10n_co_edi_type:
            constraints['l10n_co_edi_type'] = _("An Electronic Invoice Type must be selected before sending the invoice.")
        # required fields on company
        operation_mode = self._dian_get_operation_mode(move)
        if not operation_mode:
            constraints["dian_operation_modes"] = _("No DIAN Operation Mode Matches")
        else:
            mandatory_fields = ['dian_software_id', 'dian_software_operation_mode', 'dian_software_security_code']
            if move.company_id.l10n_co_dian_test_environment:
                mandatory_fields.append('dian_testing_id')
            for field in mandatory_fields:
                constraints[field] = self._check_required_fields(operation_mode, field)
            if move.l10n_co_dian_identifier_type in ('cude', 'cuds') and not operation_mode.dian_software_security_code:
                constraints['l10n_co_dian_identifier_type'] = _("The software PIN is required to compute the CUDE/CUDS.")
        # required fields on journal
        if move.move_type == 'out_invoice' and not move.journal_id.l10n_co_dian_technical_key and not move.company_id.l10n_co_dian_demo_mode:
            constraints['l10n_co_dian_technical_key'] = _("A technical key on the journal is required to compute the CUFE.")
        for field in (['l10n_co_edi_dian_authorization_number', 'l10n_co_edi_dian_authorization_date',
                      'l10n_co_edi_dian_authorization_end_date', 'l10n_co_edi_min_range_number',
                      'l10n_co_edi_max_range_number'] + ['l10n_co_dian_technical_key'] if not move.company_id.l10n_co_dian_demo_mode else []):
            constraints[f"dian_{field}"] = self._check_required_fields(move.journal_id, field)
        # fields on partners
        for role in ('customer', 'supplier'):
            commercial_partner = vals[role].commercial_partner_id
            constraints.update({
                f"dian_vat_{role}": self._check_required_fields(commercial_partner, 'vat'),
                f"dian_identification_type_{role}": self._check_required_fields(commercial_partner, 'l10n_latam_identification_type_id'),
                f"dian_obligation_type_{role}": self._check_required_fields(commercial_partner, 'l10n_co_edi_obligation_type_ids'),
            })
            if commercial_partner.l10n_latam_identification_type_id.l10n_co_document_code != 'rut' and commercial_partner.vat and '-' in commercial_partner.vat:
                constraints[f"dian_NIT_{role}"] = _("The identification number of %s contains '-' but is not a NIT.", commercial_partner.name)
            if vals[role].country_code == 'CO' and commercial_partner.vat != FINAL_CONSUMER_VAT:
                constraints[f'dian_country_subentity_{role}'] = self._check_required_fields(vals[role], 'state_id')
                constraints[f"dian_city_{role}"] = self._check_required_fields(vals[role], 'city_id')
        # fields on lines
        for line in move.invoice_line_ids.filtered(lambda l: l.display_type not in ('line_section', 'line_subsection', 'line_note')):
            product = line.product_id
            constraints[f"product_{product.id}"] = self._check_required_fields(
                product, ['default_code', 'barcode', 'unspsc_code_id'])
            if move.l10n_co_edi_type == L10N_CO_EDI_TYPE['Export Invoice'] and product:
                if not product.l10n_co_edi_customs_code:
                    constraints['dian_export_product_code'] = _("Every exportation product must have a customs code.")
                if not product.l10n_co_edi_brand:
                    constraints['dian_export_product_brand'] = _("Every exportation product must have a brand.")
            if "IBUA" in line.tax_ids.l10n_co_edi_type.mapped('name') and product.l10n_co_edi_ref_nominal_tax == 0:
                constraints['dian_sugar'] = _(
                    "Volume in milliliters should be set on the %(field_description)s field for product: %(product_name)s when using IBUA taxes.",
                    field_description=product._fields['l10n_co_edi_ref_nominal_tax']._description_string(self.env),
                    product_name=product.name)
            if "ICL" in line.tax_ids.l10n_co_edi_type.mapped('name') and product.l10n_co_edi_ref_nominal_tax == 0:
                constraints['dian_alcohol'] = _(
                    "Alcohol percentage should be set on the %(field_description)s field for product: %(product_name)s when using ICL taxes.",
                    field_description=product._fields['l10n_co_edi_ref_nominal_tax']._description_string(self.env),
                    product_name=product.name)
            if move.l10n_co_edi_is_support_document and move.currency_id.is_zero(line.price_unit):
                constraints['dian_zero_lines'] = _("Every lines should have non zero price units.")

        if move.l10n_co_edi_operation_type == '20':
            # Credit note with a referenced invoice
            if not move.l10n_co_edi_description_code_credit:
                constraints['dian_credit_note_missing_reason'] = _("Please set a credit note reason as it is required for this type of transaction.")
            if not move.reversed_entry_id:
                constraints['dian_credit_note'] = _("There is no invoice linked to this credit note but the operation type is '20'.")
            elif not move.reversed_entry_id.l10n_co_edi_cufe_cude_ref:
                constraints['dian_credit_note_cufe'] = _("The invoice linked to this credit note has no CUFE.")

        if move.move_type == 'in_refund':
            # Support Document Credit Note
            if not move.reversed_entry_id:
                constraints['dian_credit_note'] = _("There is no support document linked to this credit note.")
            if not move.reversed_entry_id.l10n_co_edi_cufe_cude_ref:
                constraints['dian_credit_note_cufe'] = _("The support document linked to this credit note has no CUDS.")

        if move.l10n_co_edi_operation_type == '30':
            # Debit note with a referenced invoice
            if not move.debit_origin_id:
                constraints['dian_debit_note'] = _("There is no original debited invoice but the operation type is '30'.")
            elif not move.debit_origin_id.l10n_co_edi_cufe_cude_ref:
                constraints['dian_debit_note_cufe'] = _("The original debited invoice has no CUFE.")

        if move.l10n_co_edi_operation_type in ('20', '22'):
            constraints['dian_concepto_credit_note'] = self._check_required_fields(move, 'l10n_co_edi_description_code_credit')
        if move.l10n_co_edi_debit_note:
            constraints['dian_concepto_debit_note'] = self._check_required_fields(move, 'l10n_co_edi_description_code_debit')

        if move.l10n_co_edi_operation_type == '09':
            if set(move.line_ids.mapped('product_id.type')) != {'service'}:
                constraints['dian_aiu_products'] = _("All products in an AIU invoice should be a service.")
        return constraints

    # -------------------------------------------------------------------------
    # EXPORT: Commercial Events
    # -------------------------------------------------------------------------

    def _export_co_send_event_update_status_invoice(self, invoice, next_commercial_state):
        # 1. Instantiate the XML builder
        vals = {'invoice': invoice, 'l10n_co_dian_commercial_state_next': next_commercial_state}
        document_node = self._get_co_invoice_event_update_status_node(vals)
        document_nsmap = self._get_co_invoice_event_update_status_nsmap(vals)

        # 2. Render the XML
        xml_content = dict_to_xml(document_node, nsmap=document_nsmap)

        # 3. Format the XML
        xml = etree.tostring(xml_content, xml_declaration=True, encoding='UTF-8')
        return self.with_context(l10n_co_next_commercial_state=next_commercial_state)._dian_sign_xml(xml, invoice)

    def _get_co_invoice_event_update_status_node(self, vals):
        self._add_co_invoice_event_update_status_config_vals(vals)

        document_node = {'_tag': 'ApplicationResponse'}
        self._add_co_invoice_event_update_status_header_nodes(document_node, vals)
        self._add_co_invoice_event_update_status_note_nodes(document_node, vals)
        self._add_co_invoice_event_update_status_sender_party_nodes(document_node, vals)
        self._add_co_invoice_event_update_status_receiver_party_nodes(document_node, vals)
        self._add_co_invoice_event_update_status_document_response_nodes(document_node, vals)

        document_node['cbc:UUID']['_text'] = self._dian_calculate_cude_sha384(document_node, vals)

        return document_node

    def _add_co_invoice_event_update_status_config_vals(self, vals):
        invoice = vals['invoice']
        vals.update({
            'now': datetime.now(tz=timezone('America/Bogota')),
            'sender_partner': invoice.company_id.partner_id,
            'receiver_partner': invoice.partner_id,
            'is_test_env': invoice.company_id.l10n_co_dian_test_environment,
            'tax_types': invoice.line_ids.tax_ids.flatten_taxes_hierarchy().mapped('l10n_co_edi_type'),
        })

    def _add_co_invoice_event_update_status_header_nodes(self, node, vals):
        invoice = vals['invoice']
        commercial_state_values = invoice._fields['l10n_co_dian_commercial_state'].get_values(self.env)
        if invoice.is_purchase_document():
            id_prefix = invoice.ref
        else:
            id_prefix = invoice.name

        node.update({
            'cbc:UBLVersionID': {'_text': 'UBL 2.1'},
            'cbc:CustomizationID': {'_text': '1'},
            'cbc:ProfileID': {'_text': 'DIAN 2.1: ApplicationResponse de la Factura Electrónica de Venta'},
            'cbc:ProfileExecutionID': {'_text': '2' if vals['is_test_env'] else '1'},
            'cbc:ID': {
                # the move id suffixed by a number that increases with every call
                '_text': f'{id_prefix}{commercial_state_values.index(vals["l10n_co_dian_commercial_state_next"])}',
            },
            'cbc:UUID': {
                'schemeID': '2' if vals['is_test_env'] else '1',
                'schemeName': 'CUDE-SHA384',
            },
            'cbc:IssueDate': {'_text': vals['now'].date().isoformat()},
            'cbc:IssueTime': {'_text': vals['now'].strftime("%H:%M:%S-05:00")},
        })

    def _add_co_invoice_event_update_status_note_nodes(self, node, vals):
        invoice = vals['invoice']
        if invoice.move_type in ('out_invoice', 'out_refund') and vals['l10n_co_dian_commercial_state_next'] == 'accepted_by_issuer':
            last_event_xml = etree.fromstring(invoice.l10n_co_dian_document_ids.sorted()[0].attachment_id.raw)
            last_event_cufe = last_event_xml.findtext('./{*}UUID')
            node.update({
                'cbc:Note': {
                    '_text': f"""Manifiesto bajo la gravedad de juramento que transcurridos 3 días hábiles contados desde la creación del Recibo de bienes
y servicios {invoice.name} con CUDE {last_event_cufe}, el adquirente {invoice.partner_id.name} identificado con NIT {invoice.partner_id.vat} no manifestó expresamente
la aceptación o rechazo de la referida factura, ni reclamó en contra de su contenido.""",
                }
            })

    def _add_co_invoice_event_update_status_sender_party_nodes(self, node, vals):
        node['cac:SenderParty'] = {
            'cac:PartyTaxScheme': self._get_co_invoice_event_update_status_party_tax_scheme_node({**vals, 'partner': vals['sender_partner'], 'role': 'sender'}),
        }

    def _add_co_invoice_event_update_status_receiver_party_nodes(self, node, vals):
        receiver_partner = vals['receiver_partner']
        node['cac:ReceiverParty'] = {
            'cac:PartyTaxScheme': self._get_co_invoice_event_update_status_party_tax_scheme_node({**vals, 'partner': receiver_partner, 'role': 'receiver'}),
        }

        if vals['l10n_co_dian_commercial_state_next'] != 'accepted_by_issuer':
            node['cac:ReceiverParty']['cac:Contact'] = {
                'cbc:ElectronicMail': {'_text': receiver_partner.email},
            }

    def _get_co_invoice_event_update_status_party_tax_scheme_node(self, vals):
        partner = vals['partner']

        if vals['role'] == 'sender':
            registration_name = partner.display_name
        elif vals['l10n_co_dian_commercial_state_next'] != 'accepted_by_issuer':
            registration_name = partner.name
        else:
            registration_name = "Unidad Administrativa Especial Dirección de Impuestos y Aduanas Nacionales"

        tax_type = vals['tax_types'][0] if vals['tax_types'] else None

        if vals['role'] == 'sender' and vals['l10n_co_dian_commercial_state_next'] == 'accepted_by_issuer':
            partner_vat = '800197268'  # VAT number of DIAN
        else:
            partner_vat = partner._get_vat_without_verification_code()

        return {
            'cbc:RegistrationName': {'_text': registration_name},
            'cbc:CompanyID': {
                '_text': partner_vat,
                'schemeName': partner._l10n_co_edi_get_carvajal_code_for_identification_type(),
                'schemeAgencyName': "CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)",
                'schemeAgencyID': "195",
                'schemeID': partner._get_vat_verification_code(),
                'schemeVersionID': "1",
            },
            'cac:TaxScheme': {
                'cbc:ID': {'_text': tax_type.code if tax_type else None},
                'cbc:Name': {'_text': tax_type.name if tax_type else None},
            },
        }

    def _add_co_invoice_event_update_status_document_response_nodes(self, node, vals):
        node['cac:DocumentResponse'] = {
            'cac:Response': self._get_co_invoice_event_update_status_response_node(vals),
            'cac:DocumentReference': self._get_co_invoice_event_update_status_document_reference_node(vals),
        }

        if vals['l10n_co_dian_commercial_state_next'] in ('received', 'goods_received'):
            node['cac:DocumentResponse']['cac:IssuerParty'] = self._get_co_invoice_event_update_status_issuer_party_node(vals)

    def _get_co_invoice_event_update_status_response_node(self, vals):
        invoice = vals['invoice']

        match vals['l10n_co_dian_commercial_state_next']:
            case 'received':
                description = "Acuse de recibo de Factura Electrónica de Venta"
            case 'goods_received':
                description = "Recibo del bien y/o prestación del servicio"
            case 'claimed':
                description = "Reclamo de la Factura Electrónica de Venta"
            case 'accepted':
                description = "Aceptación expresa"
            case 'accepted_by_issuer':
                description = "Aceptación Tácita"
            case unknown_state:
                _logger.warning(_("Unknown commercial state %(state)s", state=unknown_state))
                description = None

        commercial_states = dict(invoice._fields['l10n_co_dian_commercial_state']._description_selection(self.env))

        node = {
            'cbc:ResponseCode': {
                '_text': commercial_states[vals['l10n_co_dian_commercial_state_next']].split(' - ', 1)[0],
            },
            'cbc:Description': {'_text': description},
        }

        if vals['l10n_co_dian_commercial_state_next'] == 'claimed':
            # DIAN expects the claim reason names in Spanish
            claim_reasons = invoice._fields['l10n_co_dian_claim_reason']._description_selection(self.with_context(lang='es_419').env)
            node['cbc:ResponseCode'].update({
                'listID': invoice.l10n_co_dian_claim_reason,
                'name': next(v for k, v in claim_reasons if k == invoice.l10n_co_dian_claim_reason),
            })

        return node

    def _get_co_invoice_event_update_status_document_reference_node(self, vals):
        invoice = vals['invoice']
        return {
            'cbc:ID': {'_text': invoice.name if invoice.move_type == 'out_invoice' else invoice.ref},
            'cbc:UUID': {
                '_text': invoice.l10n_co_edi_cufe_cude_ref,
                'schemeName': 'CUFE-SHA384',
            },
            'cbc:DocumentTypeCode': {'_text': invoice.l10n_co_edi_type.zfill(2)}
        }

    def _get_co_invoice_event_update_status_issuer_party_node(self, vals):
        partner = vals['invoice'].partner_id
        node = {
            'cac:Person': {
                'cbc:ID': {
                    '_text': compact(partner.vat),
                    'schemeName': partner._l10n_co_edi_get_carvajal_code_for_identification_type(),
                    'schemeID': partner.vat,
                },
                'cbc:FirstName': {'_text': partner.name},
                'cbc:FamilyName': {'_text': partner.name},
            }
        }

        if partner.function:
            node['cac:Person'].update({
                'cbc:JobTitle': {'_text': partner.function},
                'cbc:OrganizationDepartment': {'_text': partner.function},
            })

        return node

    def _get_co_invoice_event_update_status_nsmap(self, vals):
        return {
            None: 'urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2',
            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'ds': 'http://www.w3.org/2000/09/xmldsig#',
            'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
            'sts': 'dian:gov:co:facturaelectronica:Structures-2-1',
            'xades': 'http://uri.etsi.org/01903/v1.3.2#',
            'xades141': 'http://uri.etsi.org/01903/v1.4.1#',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        }

    # -------------------------------------------------------------------------
    # Utils
    # -------------------------------------------------------------------------

    def _dian_insert_corporate_registration_scheme_node(self, invoice, xml):
        # Create a CorporateRegistrationScheme node
        root = etree.fromstring(xml)
        nsmap = root.nsmap
        corporate_node = etree.Element("{%s}CorporateRegistrationScheme" % nsmap.get('cac'), nsmap=nsmap)
        id_node = etree.SubElement(corporate_node, "{%s}ID" % nsmap.get('cbc'), nsmap=nsmap)
        id_node.text = invoice.journal_id.code
        name_node = etree.SubElement(corporate_node, "{%s}Name" % nsmap.get('cbc'), nsmap=nsmap)
        name_node.text = invoice.company_id.partner_id._get_vat_without_verification_code()
        # Insert
        legal_entity_node = root.find('.//{*}AccountingSupplierParty//{*}PartyLegalEntity')
        if legal_entity_node is not None:
            legal_entity_node.insert(2, corporate_node)
        return etree.tostring(cleanup_xml_node(root))

    def _dian_get_qr_code_url(self, invoice, identifier):
        """ Returns the value used to fill the sts:DianExtensions/sts:QRCode node """
        if invoice.company_id.l10n_co_dian_test_environment:
            url = 'https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey='
        else:
            url = 'https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey='
        return url + identifier

    def _dian_get_security_code(self, operation_mode, document_number):
        """ Returns the value for the 'SoftwareSecurityCode' node """
        return sha384((
            operation_mode.dian_software_id
            + operation_mode.dian_software_security_code
            + document_number
        ).encode()).hexdigest()

    def _dian_get_document_type_code(self, invoice):
        """ Returns the document type, used for the 'InvoiceTypeCode'/'CreditNoteTypeCode' node """
        if not invoice.l10n_co_edi_is_support_document and invoice.l10n_co_edi_type:
            return invoice.l10n_co_edi_type
        elif invoice.move_type == 'in_refund':
            return '95'  # Nota de ajuste al documento soporte
        else:
            return '05'  # Documento soporte

    def _dian_get_customization_id(self, invoice):
        """ Returns the value used for the 'CustomizationID' node """
        if not invoice.l10n_co_edi_is_support_document:
            return invoice.l10n_co_edi_operation_type
        return '10' if invoice.partner_id.country_code == 'CO' else '11'

    def _dian_get_operation_mode(self, invoice):
        """Looks for the desired operation mode record based on the mode type"""
        # use 'invoice' for invoices and vendor bills that are not support documents
        mode = 'bill' if invoice.journal_id.l10n_co_edi_is_support_document else 'invoice'
        return invoice.company_id.l10n_co_dian_operation_mode_ids.filtered(
            lambda operation_mode: operation_mode.dian_software_operation_mode == mode
        )

    def _get_sts_namespace(self, invoice):
        if invoice.l10n_co_edi_debit_note or invoice.move_type == 'out_refund':
            return "http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures"
        else:
            return "dian:gov:co:facturaelectronica:Structures-2-1"

    @api.model
    def _dian_calculate_cude_sha384(self, node, vals):
        """Compute the CUDE for a move
        type: 'application_response'
        see: Section 11.5 of Anexo-Tecnico-Factura-Electronica-de-Venta-vr-1-9
        """
        cude_vals = {
            'Num_DE': node['cbc:ID']['_text'],
            'Fec_Emi': node['cbc:IssueDate']['_text'],
            'Hor_Emi': node['cbc:IssueTime']['_text'],
            'NitFe': node['cac:SenderParty']['cac:PartyTaxScheme']['cbc:CompanyID']['_text'],
            'DocAdq': node['cac:ReceiverParty']['cac:PartyTaxScheme']['cbc:CompanyID']['_text'],
            'ResponseCode': node['cac:DocumentResponse']['cac:Response']['cbc:ResponseCode']['_text'],
            'ID': node['cac:DocumentResponse']['cac:DocumentReference']['cbc:ID']['_text'],
            'DocumentTypeCode': node['cac:DocumentResponse']['cac:DocumentReference']['cbc:DocumentTypeCode']['_text'],
            'Software-PIN': self._dian_get_operation_mode(vals['invoice']).dian_software_security_code,
        }

        cude = ''.join(str(value) for value in cude_vals.values())
        return sha384(cude.encode()).hexdigest()

    def _dian_sign_xml(self, xml, invoice):
        errors = []
        certificates_sudo = invoice.company_id.sudo().l10n_co_dian_certificate_ids
        operation_mode = self._dian_get_operation_mode(invoice)
        x509_certificates = []
        for cert_sudo in certificates_sudo:
            x509_certificates.append({
                'x509_issuer_description': cert_sudo._get_issuer_string(),
                'x509_serial_number': int(cert_sudo.serial_number),
            })
        root = etree.fromstring(xml)
        namespaces = root.nsmap
        document_number = root.findtext('./cbc:ID', namespaces=namespaces)

        if ((invoice.move_type in ('in_invoice', 'in_refund') and not invoice.l10n_co_edi_is_support_document)
                or (invoice.move_type == 'out_invoice' and self.env.context.get('l10n_co_next_commercial_state') == 'accepted_by_issuer')):
            identifier = root.findtext('.//cac:DocumentResponse/cac:DocumentReference/cbc:UUID', namespaces=namespaces)
        else:
            identifier = root.findtext('./cbc:UUID', namespaces=namespaces)

        signature_vals = {
            'record': invoice,
            'sts_namespace': self._get_sts_namespace(invoice),
            'provider_check_digit': invoice.company_id.partner_id._get_vat_verification_code(),
            'provider_id': invoice.company_id.partner_id._get_vat_without_verification_code(),
            'software_id': operation_mode.dian_software_id,
            'software_security_code': self._dian_get_security_code(operation_mode, document_number),
            'qr_code_val': self._dian_get_qr_code_url(invoice, identifier),
            'document_id': "xmldsig-" + str(xml_utils._uuid1()),
            'key_info_id': "xmldsig-" + str(xml_utils._uuid1()) + "-keyinfo",
            'x509_certificate': cert_sudo._get_der_certificate_bytes().decode(),
            'x509_certificates': x509_certificates,
            'signature_value': 'to be filled later',
            # Colombia time (UTC-5): p.556 "Anexo-Tecnico-Resolucion[...].pdf"
            'signing_time': datetime.now(tz=timezone('America/Bogota')).isoformat(timespec='milliseconds'),
            'sigcertif_digest': cert_sudo._get_fingerprint_bytes(formatting='base64').decode(),
            'claimed_role': "supplier",
        }
        extensions = self.env['ir.qweb']._render('l10n_co_dian.ubl_extension_dian', signature_vals)
        extensions = cleanup_xml_node(extensions, remove_blank_nodes=False)
        root.insert(0, extensions)
        xml_utils._remove_tail_and_text_in_hierarchy(root)
        # Hash and sign
        xml_utils._reference_digests(extensions.find(".//ds:SignedInfo", {'ds': 'http://www.w3.org/2000/09/xmldsig#'}))
        xml_utils._fill_signature(extensions.find(".//ds:Signature", {'ds': 'http://www.w3.org/2000/09/xmldsig#'}), cert_sudo)
        return etree.tostring(root, encoding='UTF-8'), errors

    # -------------------------------------------------------------------------
    # IMPORT
    # -------------------------------------------------------------------------

    def _import_fill_invoice(self, invoice, tree, qty_factor):
        # OVERRIDE account.edi.xml.ubl_20
        logs = super()._import_fill_invoice(invoice, tree, qty_factor)
        cufe = self._find_value("./cbc:UUID[@schemeName='CUFE-SHA384']", tree)
        if cufe:
            invoice.l10n_co_edi_cufe_cude_ref = cufe
        if invoice.is_purchase_document():
            self.env['l10n_co_dian.document']._create_document(
                etree.tostring(tree, encoding='UTF-8'),
                invoice,
                'invoice_accepted',
                attachment_name=f'dian_{invoice.move_type}_{invoice.ref}.xml',
                commercial_state='pending',
                message_json={'status': ''},
            )
        return logs
