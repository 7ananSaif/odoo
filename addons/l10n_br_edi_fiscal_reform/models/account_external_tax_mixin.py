# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api


class AccountExternalTaxMixin(models.AbstractModel):
    _inherit = "account.external.tax.mixin"

    l10n_br_presence = fields.Selection(
        # Technical selection names are compatible with the API.
        [
            ('0', 'Not applicable'),
            ('1', 'Present'),
            ('2', 'Remote, internet'),
            ('3', 'Remote, phone'),
            ('4', 'NFC-e home delivery'),
            ('5', 'In-person operation, for establishment (v3)'),
            ('9', 'Remote, others'),
        ],
        compute='_compute_l10n_br_presence',
        store=True,
        readonly=False,
        string='Presence',
        help='Brazil: Defines if the buyer was physically present during the transaction, affecting tax calculation and location.'
    )

    def _compute_l10n_br_presence(self):
        # To override elsewhere.
        for record in self:
            record.l10n_br_presence = '1'

    def _l10n_br_get_partner_type(self, partner):
        # Override.
        if not self.company_id.l10n_br_is_icbs:
            return super()._l10n_br_get_partner_type(partner)

        return partner.l10n_br_entity_type or super()._l10n_br_get_partner_type(partner)

    def _get_l10n_br_avatax_service_params(self):
        # Override.
        params = super()._get_l10n_br_avatax_service_params()
        if not params['company'].l10n_br_is_icbs:
            return params

        params['presence'] = self.l10n_br_presence
        return params

    @api.model
    def _prepare_l10n_br_avatax_document_line_service_call(self, line_data, record_use_type, cnae, is_service, partner_shipping, company):
        # Override.
        res = super()._prepare_l10n_br_avatax_document_line_service_call(line_data, record_use_type, cnae, is_service, partner_shipping, company)
        if not company.l10n_br_is_icbs:
            return res

        base_line = line_data['base_line']
        product = base_line['product_id']

        descriptor = res['itemDescriptor']
        if legal_reference := product.l10n_br_ncm_code_id.legal_reference:
            descriptor['legalReference'] = legal_reference

        operation_type = line_data['operation_type']
        if operation_type.has_inbound_cbs_ibs_credit:
            descriptor['appropriateCBSIBScreditWhenInBound'] = True
        if operation_type.is_used_movable_good:
            descriptor['usedMovableSupplyInd'] = True
        if operation_type.l10n_br_transaction_usage:
            res['usagePurpose'] = operation_type.l10n_br_transaction_usage

        if deduction := line_data.get('cbs_ibs_deduction'):
            deductions = res.setdefault('taxDeductions', {})
            deductions['cbsIbs'] = deduction

        if is_service:
            descriptor['hsCode'] = product.l10n_br_nbs_id.code
            descriptor['lc116Code'] = (product.l10n_br_ncm_code_id.code or '').replace('.', '')
        else:
            legal_uom = product.l10n_br_legal_uom_id
            line_uom = base_line['product_uom_id']

            goods = res.setdefault('goods', {})
            goods['notSubjectToIsTax'] = not product.l10n_br_taxable_is

            goods['customsCapitalRegimeIndicator'] = operation_type.l10n_br_customs_regime_id.name
            goods['tpCredPresIBSZFM'] = operation_type.credit_classification
            goods['donationInd'] = operation_type.is_donation

            # the maximum length allowed by the API is 6
            descriptor['unit'] = line_uom.name[:6] if line_uom else ''

            if legal_uom and line_uom:
                descriptor['unitTaxable'] = legal_uom.name[:6]
                descriptor['cbsIbsUnitFactor'] = line_uom._compute_quantity(1, legal_uom)

        return res

    @api.model
    def _l10n_br_update_location_cbs_ibs(self, location, partner):
        location.setdefault('taxesSettings', {}).update({
            'notCbsIbsTaxPayer': not partner.l10n_br_is_cbs_ibs_taxpayer,
        })
        if partner.l10n_br_tax_regime == 'simplified':
            is_normal = partner.l10n_br_is_cbs_ibs_normal
            location.setdefault('taxesSettings', {}).update(
                {
                    'cbsIbsTaxPayer': is_normal,
                    'pCredCBSSN': 0 if is_normal else partner.l10n_br_cbs_credit,
                    'pCredIBSSN': 0 if is_normal else partner.l10n_br_ibs_credit,
                }
            )

    @api.model
    def _prepare_l10n_br_avatax_document_service_call(self, params):
        # Override.
        res = super()._prepare_l10n_br_avatax_document_service_call(params)
        if not params['company'].l10n_br_is_icbs:
            return res

        is_service = params['is_service']
        header_for_type = res['header'].setdefault('services' if is_service else 'goods', {})
        header_for_type['enableCalcICBS'] = True  # enables fiscal reform

        if not is_service and (presence := params.get('presence')):
            header_for_type['indPres'] = presence
            if presence in ('2', '3', '9'):
                header_for_type['indIntermed'] = '0'

        locations = res['header']['locations']
        self._l10n_br_update_location_cbs_ibs(locations['establishment'], params['company_partner'])

        entity_partner = params['partner']
        entity_location = locations['entity']
        self._l10n_br_update_location_cbs_ibs(entity_location, entity_partner)

        if is_service:
            partner_shipping_id = params['partner_shipping']
            locations.setdefault('rendered', {}).update({
                'address': {
                    'number': partner_shipping_id.street_number,
                    'street': partner_shipping_id.street,
                    'neighborhood': partner_shipping_id.street2,
                    'zipcode': partner_shipping_id.zip,
                    'cityName': partner_shipping_id.city,
                    'state': partner_shipping_id.state_id.code,
                }
            })

            if service_operation := params['operation_type'].l10n_br_service_operation_indicator:
                res['header'].setdefault('services', {})['indOp'] = service_operation

        if entity_partner.l10n_br_tax_regime == 'individual':
            taxes_settings_entity = entity_location.setdefault('taxesSettings', {})
            taxes_settings_entity['applyCashback'] = entity_partner.l10n_br_is_cashback_applied

        return res
