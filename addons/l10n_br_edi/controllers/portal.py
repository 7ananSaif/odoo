# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request

from odoo.addons.l10n_br.controllers.portal import L10nBRPortalAccount


class L10nBREdiPortalAccount(L10nBRPortalAccount):

    def _complete_address_values(self, address_values, *args, **kwargs):
        """ Override. Complete the address for EDI in the B2C case (CPF identification). """
        super()._complete_address_values(address_values, *args, **kwargs)
        if address_values.get('l10n_latam_identification_type_id') == request.env.ref('l10n_br.cpf').id:
            fiscal_position = request.env['account.fiscal.position'].sudo().search([
                ('company_id', '=', request.env.company.id), ('l10n_br_is_avatax', '=', True)
            ], limit=1)
            address_values.update({
                'property_account_position_id': fiscal_position.id,
                'l10n_br_tax_regime': 'individual',
                'l10n_br_taxpayer': 'non',
                'l10n_br_activity_sector': 'finalConsumer',
                'l10n_br_subject_cofins': 'T',
                'l10n_br_subject_pis': 'T',
                'l10n_br_is_subject_csll': True,
            })
