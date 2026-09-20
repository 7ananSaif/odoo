from odoo import models, _


class AccountEdiXmlUBLDianMandate(models.AbstractModel):
    _inherit = 'account.edi.xml.ubl_dian'
    _description = "UBL DIAN Mandate extension"

    def _add_invoice_line_id_nodes(self, line_node, vals):
        super()._add_invoice_line_id_nodes(line_node, vals)
        base_line = vals['base_line']
        invoice = vals['invoice']
        if invoice.l10n_co_edi_operation_type == '11':
            line_node['cbc:ID']['schemeID'] = '1' if base_line['product_id'].l10n_co_dian_mandate_contract else '0'

    def _add_invoice_line_item_nodes(self, line_node, vals):
        super()._add_invoice_line_item_nodes(line_node, vals)
        product = vals['base_line']['product_id']
        invoice = vals['invoice']
        if product.l10n_co_dian_mandate_contract and invoice.l10n_co_dian_mandate_principal:
            scheme_name_mp = invoice.l10n_co_dian_mandate_principal._l10n_co_edi_get_carvajal_code_for_identification_type()
            line_node['cac:Item']['cac:InformationContentProviderParty'] = {
                'cac:PowerOfAttorney': {
                    'cac:AgentParty': {
                        'cac:PartyIdentification': {
                            'cbc:ID': {
                                '_text': invoice.l10n_co_dian_mandate_principal._get_vat_without_verification_code(),
                                'schemeAgencyID': '195',
                                'schemeAgencyName': "CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)",
                                'schemeID': invoice.l10n_co_dian_mandate_principal._get_vat_verification_code() if scheme_name_mp == '31' else False,
                                'schemeName': scheme_name_mp,
                            }
                        }
                    }
                }
            }

    def _export_invoice_constraints(self, move, vals):
        constraints = super()._export_invoice_constraints(move, vals)

        should_be_mandate = (
            move.move_type in ('in_invoice', 'out_invoice')
            and not move.journal_id.l10n_co_edi_debit_note
            and move.line_ids.product_id.filtered('l10n_co_dian_mandate_contract')
        )

        if move.l10n_co_edi_operation_type != '11' and should_be_mandate:
            constraints['dian_mandate_products'] = _(
                "One or more products in the invoice are marked as Mandate Contracts. "
                "Please select 'Mandatos' as the Operation Type (CO), or remove those products from the invoice."
            )

        if move.l10n_co_edi_operation_type == '11' and not should_be_mandate:
            constraints['dian_not_mandate_products'] = _(
                "The 'Mandatos' option was selected as the Operation Type (CO), but the invoice does not contain "
                "any products marked as Mandate Contracts. Adjust the invoice type or check the listed products."
            )
        return constraints
