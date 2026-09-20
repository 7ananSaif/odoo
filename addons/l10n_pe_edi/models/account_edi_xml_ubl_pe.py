import re

from odoo import models

# These codes correspond to the tax affectation reasons used in Peru for
# issuing free invoices according to SUNAT regulations. Invoices with these
# codes are considered "gratuitas" (free), meaning that no payment is expected
# for the goods or services provided, typically in cases like promotions,
# donations, or samples.
FREE_AFFECTATION_REASONS = ['11', '12', '13', '14', '15', '16', '21', '31', '32', '33', '34', '35', '36']


class AccountEdiXmlUbl_Pe(models.AbstractModel):
    _name = 'account.edi.xml.ubl_pe'
    _inherit = ['account.edi.xml.ubl_21']
    _description = 'PE UBL 2.1'

    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------

    def _export_invoice_filename(self, invoice):
        return f"{invoice.name.replace('/', '_')}_ubl_pe.xml"

    def _add_invoice_base_lines_vals(self, vals):
        super()._add_invoice_base_lines_vals(vals)
        invoice = vals['invoice']

        # Filter out prepayment lines of final invoices
        vals['prepayment_lines'] = []
        cleaned_base_lines = []
        if not invoice._is_downpayment():
            for base_line in vals['base_lines']:
                if base_line['record']._get_downpayment_lines():
                    vals['prepayment_lines'].append(base_line)
                else:
                    cleaned_base_lines.append(base_line)
            vals['base_lines'] = cleaned_base_lines

    def _is_document_allowance_charge(self, base_line):
        """ Negative lines (global discounts) should be treated as document-level AllowanceCharges. """
        return super()._is_document_allowance_charge(base_line) or base_line['tax_details']['total_excluded_currency'] < 0

    def _add_document_tax_grouping_function_vals(self, vals):
        super()._add_document_tax_grouping_function_vals(vals)

        withholding_group_id = self.env['account.chart.template'].with_company(vals['invoice'].company_id).ref('tax_group_igv_withholding', raise_if_not_found=False)

        original_total_grouping_function = vals['total_grouping_function']
        original_tax_grouping_function = vals['tax_grouping_function']

        # Always ignore withholding taxes in the UBL
        def total_grouping_function(base_line, tax_data):
            if tax_data and tax_data['tax'].tax_group_id == withholding_group_id:
                return None
            return original_total_grouping_function(base_line, tax_data)

        def tax_grouping_function(base_line, tax_data):
            # Ignore withholding taxes
            if tax_data and tax_data['tax'].tax_group_id == withholding_group_id:
                return None
            return original_tax_grouping_function(base_line, tax_data)

        vals['total_grouping_function'] = total_grouping_function
        vals['tax_grouping_function'] = tax_grouping_function

    # -------------------------------------------------------------------------
    # EXPORT: Templates for document header nodes
    # -------------------------------------------------------------------------

    def _add_invoice_header_nodes(self, document_node, vals):
        super()._add_invoice_header_nodes(document_node, vals)

        invoice = vals['invoice']

        document_node.update({
            'cbc:CustomizationID': {'_text': '2.0'},
            'cbc:ID': {'_text': invoice.name.replace(' ', '')},
        })

        if vals['document_type'] == 'invoice':
            document_node['cbc:InvoiceTypeCode'] = {
                '_text': invoice.l10n_latam_document_type_id.code,
                'listAgencyName': 'PE:SUNAT',
                'listID': invoice.l10n_pe_edi_operation_type,
                'listName': 'Tipo de Documento',
                'listURI': 'urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01',
            }

        if document_node['cbc:Note']:
            document_node['cbc:Note']['_text'] = re.sub(r'[^\s ]+', ' ', document_node['cbc:Note']['_text']).strip()[:200]

        if vals['document_type'] == 'invoice':
            document_node['cbc:Note'] = [document_node['cbc:Note']]

            if invoice.l10n_pe_edi_legend_value:
                document_node['cbc:Note'].append({
                    '_text': invoice.l10n_pe_edi_legend_value,
                    'languageLocaleID': '1002',
                })
            document_node['cbc:Note'].append({
                '_text': invoice._l10n_pe_edi_amount_to_text(),
                'languageLocaleID': '1000',
            })
            if invoice.l10n_pe_edi_operation_type == '1001':
                document_node['cbc:Note'].append({
                    '_text': 'Leyenda: Operacion sujeta a detraccion',
                    'languageLocaleID': '2006',
                })

        if vals['document_type'] == 'credit_note' and invoice.l10n_latam_document_type_id.code == '07':
            document_node['cac:DiscrepancyResponse'] = {
                'cbc:ResponseCode': {'_text': invoice.l10n_pe_edi_refund_reason},
                'cbc:Description': {'_text': invoice.ref},
            }
        elif vals['document_type'] == 'debit_note' and invoice.l10n_latam_document_type_id.code == '08':
            document_node['cac:DiscrepancyResponse'] = {
                'cbc:ResponseCode': {'_text': invoice.l10n_pe_edi_charge_reason},
                'cbc:Description': {'_text': invoice.ref},
            }

        if reference_document := (
            invoice.reversed_entry_id if vals['document_type'] == 'credit_note'
            else invoice.debit_origin_id if vals['document_type'] == 'debit_note'
            else None
        ):
            document_node['cac:BillingReference'] = {
                'cac:InvoiceDocumentReference': {
                    'cbc:ID': {'_text': reference_document.name.replace(' ', '')},
                    'cbc:DocumentTypeCode': {'_text': reference_document.l10n_latam_document_type_id.code},
                }
            }

        document_node['cac:Signature'] = {
            'cbc:ID': {'_text': 'IDSignKG'},
            'cac:SignatoryParty': {
                'cac:PartyIdentification': {
                    'cbc:ID': {'_text': invoice.company_id.vat}
                },
                'cac:PartyName': {
                    'cbc:Name': {'_text': invoice.company_id.name.upper()}
                }
            },
            'cac:DigitalSignatureAttachment': {
                'cac:ExternalReference': {
                    'cbc:URI': {'_text': '#SignVX'}
                }
            }
        }

        if prepayments := vals.get('prepayment_lines'):
            document_references = []
            prepaid_amounts = []
            if invoice.l10n_latam_document_type_id == self.env.ref('l10n_pe.document_type02'):
                document_type_code = '03'
            else:
                document_type_code = '02'
            prepayment_sequence = 1
            for prepayment_line in prepayments:
                prepayment_moves = prepayment_line['record']._get_downpayment_lines().move_id.filtered(lambda m: m.move_type == 'out_invoice')
                document_references.extend({
                    'cbc:ID': {'_text': prepayment_move.name.replace(' ', '')},
                    'cbc:DocumentTypeCode': {'_text': document_type_code},
                    'cbc:DocumentStatusCode': {'_text': prepayment_sequence},
                    'cac:IssuerParty': {
                        'cac:PartyIdentification': {
                            'cbc:ID': {
                                '_text': invoice.company_id.vat,
                                'schemeID': invoice.company_id.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code
                            },
                        }
                    }
                } for prepayment_move in prepayment_moves)
                prepaid_amounts.extend({
                    'cbc:ID': {'_text': prepayment_sequence},
                    'cbc:PaidAmount': {
                        '_text': self.format_float(prepayment_move.amount_total, prepayment_move.currency_id.decimal_places),
                        'currencyID': prepayment_move.currency_id.name,
                    },
                } for prepayment_move in prepayment_moves)
                prepayment_sequence += 1
            document_node['cac:AdditionalDocumentReference'] = document_references
            document_node['cac:PrepaidPayment'] = prepaid_amounts

    def _add_invoice_accounting_supplier_party_nodes(self, document_node, vals):
        super()._add_invoice_accounting_supplier_party_nodes(document_node, vals)
        invoice = vals['invoice']
        supplier = invoice.company_id.partner_id.commercial_partner_id
        document_node['cac:AccountingSupplierParty']['cbc:CustomerAssignedAccountID'] = {
            '_text': supplier.vat,
        }

    def _add_invoice_accounting_customer_party_nodes(self, document_node, vals):
        super()._add_invoice_accounting_customer_party_nodes(document_node, vals)
        invoice = vals['invoice']
        customer = invoice.partner_id
        document_node['cac:AccountingCustomerParty']['cbc:AdditionalAccountID'] = {
            '_text': (
                customer.l10n_latam_identification_type_id and
                customer.l10n_latam_identification_type_id.l10n_pe_vat_code
            )
        }

    def _get_address_node(self, vals):
        partner = vals['partner']
        model = vals.get('model', 'res.partner')
        country = partner['country' if model == 'res.bank' else 'country_id']
        state = partner['state' if model == 'res.bank' else 'state_id']
        return {
            'cbc:ID': {'_text': partner.l10n_pe_district.code},
            'cbc:AddressTypeCode': None,
            'cbc:StreetName': {'_text': partner.street},
            'cbc:AdditionalStreetName': {'_text': partner.street2},
            'cbc:CityName': {'_text': partner.city},
            'cbc:PostalZone': {'_text': partner.zip},
            'cbc:CountrySubentity': {'_text': state.name},
            'cbc:CountrySubentityCode': {'_text': state.code},
            'cac:Country': {
                'cbc:IdentificationCode': {'_text': country.code},
                'cbc:Name': {'_text': country.name},
            },
        }

    def _get_party_node(self, vals):
        party_node = super()._get_party_node(vals)
        partner = vals['partner']
        party_node['cac:PartyIdentification'] = {
            'cbc:ID': {
                '_text': partner.vat,
                'schemeID': partner.l10n_latam_identification_type_id.l10n_pe_vat_code
            }
        }
        if vals['role'] == 'supplier':
            party_node['cac:PartyLegalEntity']['cac:RegistrationAddress']['cbc:AddressTypeCode'] = {
                '_text': vals['invoice'].company_id.l10n_pe_edi_address_type_code
            }
        return party_node

    def _add_invoice_payment_means_nodes(self, document_node, vals):
        invoice = vals['invoice']
        spot = invoice._l10n_pe_edi_get_spot()
        if not spot:
            return None

        document_node['cac:PaymentMeans'] = {
            'cbc:ID': {'_text': spot['id']},
            'cbc:PaymentMeansCode': {'_text': spot['payment_means_code']},
            'cac:PayeeFinancialAccount': {
                'cbc:ID': {'_text': spot['payee_financial_account']}
            }
        }

    def _add_invoice_payment_terms_nodes(self, document_node, vals):
        invoice = vals['invoice']
        spot = invoice._l10n_pe_edi_get_spot()
        if spot:
            spot_amount = spot['amount'] if invoice.currency_id == invoice.company_id.currency_id else spot['spot_amount']
        invoice_date_due_vals_list = []
        first_time = True
        for rec_line in invoice.line_ids.filtered(lambda l: l.account_type == 'asset_receivable'):
            amount = rec_line.amount_currency
            if spot and first_time:
                amount -= spot_amount
            first_time = False
            invoice_date_due_vals_list.append({
                'currency_name': rec_line.currency_id.name,
                'currency_dp': rec_line.currency_id.decimal_places,
                'amount': amount,
                'date_maturity': rec_line.date_maturity,
            })
        total_after_spot = abs(invoice.amount_total) - spot_amount if spot else abs(invoice.amount_total)
        payment_means_id = invoice._l10n_pe_edi_get_payment_means()

        payment_terms = []
        if spot:
            payment_terms.append({
                'cbc:ID': {'_text': spot['id']},
                'cbc:PaymentMeansID': {'_text': spot['payment_means_id']},
                'cbc:PaymentPercent': {'_text': spot['payment_percent']},
                'cbc:Amount': {
                    '_text': self.format_float(spot['amount'], 2),
                    'currencyID': 'PEN'
                },
            })
        if invoice.move_type not in ('out_refund', 'in_refund'):
            if payment_means_id == 'Contado':
                payment_terms.append({
                    'cbc:ID': {'_text': 'FormaPago'},
                    'cbc:PaymentMeansID': {'_text': payment_means_id}
                })
            else:
                payment_terms.append({
                    'cbc:ID': {'_text': 'FormaPago'},
                    'cbc:PaymentMeansID': {'_text': payment_means_id},
                    'cbc:Amount': {
                        '_text': self.format_float(total_after_spot, invoice.currency_id.decimal_places),
                        'currencyID': invoice.currency_id.name
                    }
                })
                for i, due_vals in enumerate(invoice_date_due_vals_list):
                    payment_terms.append({
                        'cbc:ID': {'_text': 'FormaPago'},
                        'cbc:PaymentMeansID': {'_text': f'Cuota{(i + 1):03d}'},
                        'cbc:Amount': {
                            '_text': self.format_float(due_vals['amount'], due_vals['currency_dp']),
                            'currencyID': due_vals['currency_name']
                        },
                        'cbc:PaymentDueDate': {'_text': due_vals['date_maturity']}
                    })
        document_node['cac:PaymentTerms'] = payment_terms

    # -------------------------------------------------------------------------
    # EXPORT: Templates for document amount nodes
    # -------------------------------------------------------------------------

    def _add_invoice_tax_total_nodes(self, document_node, vals):
        withholding_group_id = self.env['account.chart.template'].with_company(vals['invoice'].company_id).ref('tax_group_igv_withholding', raise_if_not_found=False)

        def tax_grouping_function(base_line, tax_data):
            if not tax_data:
                return None
            tax = tax_data['tax']
            return {
                'l10n_pe_edi_tax_group_code': tax.tax_group_id.l10n_pe_edi_code,
                'l10n_pe_edi_international_code': tax.l10n_pe_edi_international_code,
                'l10n_pe_edi_tax_code': tax.l10n_pe_edi_tax_code,
                'is_free_invoice_fake_tax': base_line['record'].move_id.l10n_pe_edi_legend == '1002' and not tax.tax_group_id.l10n_pe_edi_code,
                'is_withholding_tax': tax.tax_group_id == withholding_group_id,
            }

        invoice = vals['invoice']
        all_lines = vals['base_lines'] + vals['prepayment_lines']
        AccountTax = self.env['account.tax']
        base_lines_aggregated_tax_details = AccountTax._aggregate_base_lines_tax_details(all_lines, tax_grouping_function)
        aggregated_tax_details = AccountTax._aggregate_base_lines_aggregated_values(base_lines_aggregated_tax_details)

        total_isc_tax = sum(
            values['tax_amount_currency']
            for grouping_key, values in aggregated_tax_details.items()
            if grouping_key['l10n_pe_edi_tax_group_code'] == 'ISC'
        )

        if invoice.l10n_pe_edi_legend == '1002':
            total_tax_amount = 0.0
        else:
            total_tax_amount = sum(
                values['tax_amount_currency']
                for grouping_key, values in aggregated_tax_details.items()
                if not grouping_key['is_withholding_tax']
            )

        document_node['cac:TaxTotal'] = {
            'cbc:TaxAmount': {
                '_text': self.format_float(total_tax_amount, vals['currency_dp']),
                'currencyID': vals['currency_name']
            },
            'cac:TaxSubtotal': [
                {
                    'cbc:TaxableAmount': {
                        '_text': self.format_float(
                            tax_details['base_amount_currency'] - (
                                total_isc_tax if grouping_key['l10n_pe_edi_tax_group_code'] != 'ISC' else 0.0
                            ),
                            vals['currency_dp'],
                        ),
                        'currencyID': vals['currency_name']
                    },
                    'cbc:TaxAmount': {
                        '_text': self.format_float(tax_details['tax_amount_currency'], vals['currency_dp']),
                        'currencyID': vals['currency_name']
                    },
                    'cac:TaxCategory': self._get_tax_category_node({**vals, 'grouping_key': grouping_key}),
                }
                for grouping_key, tax_details in aggregated_tax_details.items()
                if not grouping_key['is_free_invoice_fake_tax'] and not grouping_key['is_withholding_tax']
            ]
        }

    def _add_invoice_monetary_total_nodes(self, document_node, vals):
        super()._add_invoice_monetary_total_nodes(document_node, vals)

        monetary_total_tag = 'cac:LegalMonetaryTotal' if vals['document_type'] in {'invoice', 'credit_note'} else 'cac:RequestedMonetaryTotal'
        monetary_total_node = document_node[monetary_total_tag]
        invoice = vals['invoice']

        if invoice.l10n_pe_edi_legend == '1002':
            monetary_total_node['cbc:LineExtensionAmount']['_text'] = self.format_float(0.0, vals['currency_dp'])
            monetary_total_node['cbc:TaxExclusiveAmount']['_text'] = self.format_float(sum(
                base_line['tax_details']['total_excluded_currency']
                for base_line in vals['base_lines']
            ), vals['currency_dp'])

            for tag in ['cbc:LineExtensionAmount', 'cbc:TaxInclusiveAmount']:
                monetary_total_node[tag]['_text'] = self.format_float(0.0, vals['currency_dp'])

        else:
            # Global discounts should be included in the LineExtensionAmount, not the AllowanceTotalAmount.
            monetary_total_node['cbc:LineExtensionAmount']['_text'] = monetary_total_node['cbc:TaxExclusiveAmount']['_text']

        monetary_total_node['cbc:AllowanceTotalAmount'] = monetary_total_node['cbc:ChargeTotalAmount'] = None
        prepaid_amount = 0.0
        AccountTax = self.env['account.tax']
        prepayment_lines_aggregated_tax_details = AccountTax._aggregate_base_lines_tax_details(vals['prepayment_lines'], vals['total_grouping_function'])
        prepayment_moves_total_aggregated_tax_details = AccountTax._aggregate_base_lines_aggregated_values(prepayment_lines_aggregated_tax_details)
        for grouping_key, values in prepayment_moves_total_aggregated_tax_details.items():
            # By default grouping_key will always be True, but if other code overrides it it is good to be prepared.
            if grouping_key:
                prepaid_amount += values['base_amount_currency'] + values['tax_amount_currency']

        monetary_total_node['cbc:PrepaidAmount']['_text'] = self.format_float(abs(prepaid_amount), vals['currency_dp'])
        monetary_total_node['cbc:PayableAmount']['_text'] = self.format_float(vals['tax_inclusive_amount_currency'] - abs(prepaid_amount), vals['currency_dp'])

        return monetary_total_node

    def _get_tax_category_node(self, vals):
        grouping_key = vals['grouping_key']
        return {
            'cbc:Percent': {'_text': grouping_key['amount']} if grouping_key.get('amount_type') == 'percent' else None,
            'cbc:TaxExemptionReasonCode': {'_text': grouping_key.get('tax_exemption_reason_code')},
            'cac:TaxScheme': {
                'cbc:ID': {'_text': grouping_key['l10n_pe_edi_tax_code']},
                'cbc:Name': {'_text': grouping_key['l10n_pe_edi_tax_group_code']},
                'cbc:TaxTypeCode': {'_text': grouping_key['l10n_pe_edi_international_code']},
            }
        }

    # -------------------------------------------------------------------------
    # EXPORT: Templates for document lines
    # -------------------------------------------------------------------------
    def _add_document_allowance_charge_nodes(self, document_node, vals):
        """ Prepayment lines are added to the document-level AllowanceCharge nodes. """

        original_base_lines = vals['base_lines']
        vals['base_lines'] = original_base_lines + vals['prepayment_lines']
        super()._add_document_allowance_charge_nodes(document_node, vals)
        vals['base_lines'] = original_base_lines

        withholding_node = self._get_document_withholding_node(vals)
        if withholding_node:
            document_node['cac:AllowanceCharge'].append(withholding_node)

    def _get_document_allowance_charge_node(self, vals):
        """ Generic helper to generate a document-level AllowanceCharge node given a base_line. """
        base_line = vals['base_line']
        currency_suffix = vals['currency_suffix']
        allowance_amount = base_line['tax_details'][f'total_excluded{currency_suffix}']
        if base_line['record']._get_downpayment_lines():
            # The base amount for the document level allowance node is defined as the sum of the invoice
            # plus the downpayment amount. As such we need to invert the sign of the total since the
            # sign of the line is negative.
            base_line['tax_details']['total_excluded_currency'] = -base_line['tax_details']['total_excluded_currency']

        def grouping_function_skip_discounts(base_line, tax_data):
            if base_line['tax_details']['total_excluded_currency'] < 0:
                return None
            return True

        base_lines_aggregated_tax_details = self.env['account.tax']._aggregate_base_lines_tax_details(vals['base_lines'], grouping_function_skip_discounts)
        aggregated_tax_details = self.env['account.tax']._aggregate_base_lines_aggregated_values(base_lines_aggregated_tax_details)
        base_amount = aggregated_tax_details.get(True, {}).get('total_excluded_currency', 0.0)

        def get_allowance_code(base_line):
            """
            Functionally, while tax_ids can support multiple taxes, the
            normal functional workflow is that there is only one tax. As such,
            we can always treat the first tax as the only one.
            """
            if not 'is_downpayment' in base_line['record'] or not base_line['record'].is_downpayment:
                return '02'

            affectation_map = {'10': '04', '11': '05', '12': '06'}
            tax_ids = base_line['record'].tax_ids
            for tax in tax_ids:
                if code := affectation_map.get(tax.l10n_pe_edi_affectation_reason):
                    return code
            return '02'

        return {
            'cbc:ChargeIndicator': {'_text': 'false' if allowance_amount < 0.0 else 'true'},
            'cbc:AllowanceChargeReasonCode': {'_text': get_allowance_code(base_line)},
            'cbc:MultiplierFactorNumeric': {'_text': self.format_float(abs(allowance_amount) / base_amount, 5)},
            'cbc:Amount': {
                '_text': self.format_float(abs(allowance_amount), vals['currency_dp']),
                'currencyID': vals['currency_name']
            },
            'cbc:BaseAmount': {
                '_text': self.format_float(base_amount, vals['currency_dp']),
                'currencyID': vals['currency_name']
            },
        }

    def _add_invoice_line_amount_nodes(self, line_node, vals):
        super()._add_invoice_line_amount_nodes(line_node, vals)

        base_line = vals['base_line']
        line = base_line['record']

        # Peru uses the NIU unit code for downpayment lines
        quantity_tag = self._get_tags_for_document_type(vals)['line_quantity']
        line_node[quantity_tag]['unitCode'] = 'NIU' if line._get_downpayment_lines() else base_line['product_uom_id'].l10n_pe_edi_measure_unit_code

    def _get_line_discount_allowance_charge_node(self, vals):
        # OVERRIDE account_edi_xml_ubl_20.py
        discount_node = super()._get_line_discount_allowance_charge_node(vals)

        if discount_node:
            discount_node.update({
                'cbc:AllowanceChargeReasonCode': {'_text': '00'},
                'cbc:MultiplierFactorNumeric': {'_text': self.format_float(vals['base_line']['discount'] / 100.0, 5)},
                'cbc:BaseAmount': {
                    '_text': self.format_float(vals['gross_subtotal_currency'], vals['currency_dp']),
                    'currencyID': vals['currency_name'],
                },
            })

        return discount_node

    def _add_document_line_tax_total_nodes(self, line_node, vals):
        withholding_group_id = self.env['account.chart.template'].with_company(vals['invoice'].company_id).ref('tax_group_igv_withholding', raise_if_not_found=False)

        def tax_grouping_function(base_line, tax_data):
            if not tax_data:
                return None
            tax = tax_data['tax']
            return {
                'l10n_pe_edi_tax_code': tax.l10n_pe_edi_tax_code,
                'l10n_pe_edi_tax_group_code': tax.tax_group_id.l10n_pe_edi_code,
                'l10n_pe_edi_international_code': tax.l10n_pe_edi_international_code,
                'tax_exemption_reason_code': base_line['record'].l10n_pe_edi_affectation_reason
                                            if tax.tax_group_id.l10n_pe_edi_code not in ('ISC', 'ICBPER')
                                            else None,
                'amount': tax.amount,
                'amount_type': tax.amount_type,
                # In free invoices, fake taxes are used to bring the invoice total down to zero. They should be ignored in most cases.
                'is_free_invoice_fake_tax': base_line['record'].move_id.l10n_pe_edi_legend == '1002' and not tax.tax_group_id.l10n_pe_edi_code,
                'is_withholding_tax': tax.tax_group_id == withholding_group_id,
            }

        base_line = vals['base_line']
        line = base_line['record']
        aggregated_tax_details = self.env['account.tax']._aggregate_base_line_tax_details(base_line, tax_grouping_function)

        if line.l10n_pe_edi_affectation_reason in FREE_AFFECTATION_REASONS:
            total_tax_amount = 0.0
        else:
            total_tax_amount = sum(
                values['tax_amount_currency']
                for grouping_key, values in aggregated_tax_details.items()
                if not grouping_key['is_withholding_tax']
            )

        line_node['cac:TaxTotal'] = {
            'cbc:TaxAmount': {
                '_text': self.format_float(total_tax_amount, vals['currency_dp']),
                'currencyID': vals['currency_name']
            },
            'cac:TaxSubtotal': [
                {
                    'cbc:TaxableAmount': {
                        '_text': self.format_float(values['base_amount_currency'], vals['currency_dp']),
                        'currencyID': vals['currency_name']
                    } if grouping_key['l10n_pe_edi_tax_group_code'] != 'ICBPER' else None,
                    'cbc:TaxAmount': {
                        '_text': self.format_float(values['tax_amount_currency'], vals['currency_dp']),
                        'currencyID': vals['currency_name']
                    },
                    'cbc:BaseUnitMeasure': {
                        '_text': int(base_line['quantity']),
                        'unitCode': 'NIU' if line._get_downpayment_lines() else line.product_uom_id.l10n_pe_edi_measure_unit_code,
                    } if grouping_key['l10n_pe_edi_tax_group_code'] == 'ICBPER' else None,
                    'cac:TaxCategory': self._get_tax_category_node({**vals, 'grouping_key': grouping_key})
                }
                for grouping_key, values in aggregated_tax_details.items()
                if not grouping_key['is_free_invoice_fake_tax'] and not grouping_key['is_withholding_tax']
            ]
        }

    def _add_document_line_item_nodes(self, line_node, vals):
        super()._add_document_line_item_nodes(line_node, vals)

        product = vals['base_line']['product_id']
        line_node['cac:Item']['cac:CommodityClassification'] = {
            'cbc:ItemClassificationCode': {'_text': product.unspsc_code_id.code}
        }

    def _add_document_line_tax_category_nodes(self, line_node, vals):
        # No InvoiceLine/Item/ClassifiedTaxCategory in Peru
        pass

    def _add_invoice_line_price_nodes(self, line_node, vals):
        super()._add_invoice_line_price_nodes(line_node, vals)

        base_line = vals['base_line']
        line = base_line['record']

        if line.l10n_pe_edi_affectation_reason in FREE_AFFECTATION_REASONS:
            line_node['cac:Price']['cbc:PriceAmount']['_text'] = '0.0'

    def _add_invoice_line_pricing_reference_nodes(self, line_node, vals):
        base_line = vals['base_line']
        line = base_line['record']
        product_price_dp = self.env['decimal.precision'].precision_get('Product Price')
        aggregated_tax_details = self.env['account.tax']._aggregate_base_line_tax_details(base_line, vals['tax_grouping_function'])

        total_tax_amount = sum(
            values['tax_amount_currency']
            for grouping_key, values in aggregated_tax_details.items()
            if grouping_key
        )
        total_amount = base_line['tax_details']['total_excluded_currency'] + total_tax_amount

        line_node['cac:PricingReference'] = {
            'cac:AlternativeConditionPrice': {
                'cbc:PriceAmount': {
                    '_text': self.format_float(
                        (
                            base_line['tax_details']['total_excluded_currency']
                            if line.l10n_pe_edi_affectation_reason in FREE_AFFECTATION_REASONS
                            else total_amount
                        ) / base_line['quantity'],
                        product_price_dp
                    ),
                    'currencyID': vals['currency_name']
                },
                'cbc:PriceTypeCode': {
                    '_text': (
                        '02'
                        if line.currency_id.is_zero(base_line['tax_details']['total_excluded_currency'])
                        or line.l10n_pe_edi_affectation_reason in FREE_AFFECTATION_REASONS
                        else '01'
                    )
                }
            }
        }

    def _get_document_withholding_node(self, vals):
        """Withholding taxes should appear only once as an AllowanceCharge with reason code '62'
        This is because the withholding calculations are done at the document level, not at the line level."""
        withholding_group_id = self.env['account.chart.template'].with_company(vals['invoice'].company_id).ref('tax_group_igv_withholding', raise_if_not_found=False)

        def grouping_function_wh(base_line, tax_data):
            if not tax_data:
                return None
            return tax_data['tax'] and tax_data['tax'].tax_group_id == withholding_group_id

        base_lines_aggregated_tax_details = self.env['account.tax']._aggregate_base_lines_tax_details(vals['base_lines'], grouping_function_wh)
        aggregated_tax_details = self.env['account.tax']._aggregate_base_lines_aggregated_values(base_lines_aggregated_tax_details)
        base_amount = aggregated_tax_details.get(True, {}).get('base_amount_currency', 0.0)
        allowance_amount = aggregated_tax_details.get(True, {}).get('tax_amount_currency', 0.0)

        withholding_node = {}
        if allowance_amount:
            withholding_node.update({
                'cbc:ChargeIndicator': {'_text': 'false'},
                'cbc:AllowanceChargeReasonCode': {'_text': '62'},
                'cbc:MultiplierFactorNumeric': {'_text': self.format_float(abs(allowance_amount) / base_amount, 5)},
                'cbc:Amount': {
                    '_text': self.format_float(abs(allowance_amount), vals['currency_dp']),
                    'currencyID': vals['currency_name'],
                },
                'cbc:BaseAmount': {
                    '_text': self.format_float(base_amount, vals['currency_dp']),
                    'currencyID': vals['currency_name'],
                },
            })
        return withholding_node
