# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
NON_TAXABLE_GRIDS = {'+21', '+45_BASE', '-21', '-45_BASE'}


class AccountTax(models.Model):
    _inherit = "account.tax"

    l10n_de_vat_definition_export_identifier = fields.Integer(string='L10n DE Vat Definition Export ID', compute='_compute_l10n_de_vat_definition_export_identifier', help="The ID of the VAT definition in the Fiskaly export.", store=True, readonly=False)

    @api.depends('amount', 'invoice_repartition_line_ids.tag_ids', 'refund_repartition_line_ids.tag_ids', 'company_id.l10n_de_fiskaly_api_secret')
    def _compute_l10n_de_vat_definition_export_identifier(self):
        self.get_vat_definition_export_id()

    def get_vat_definition_export_id(self):
        """ This method is used to ensure that the export definition ID is set for all taxes that are created or updated. specifically for invidual circumstances where the export ID is not set yet."""
        for tax in self:
            if not tax.company_id.is_country_germany or not tax.company_id.l10n_de_fiskaly_api_secret:
                continue
            if not tax.amount:
                all_tags = set((tax.invoice_repartition_line_ids + tax.refund_repartition_line_ids).tag_ids.mapped('name'))
                tax.l10n_de_vat_definition_export_identifier = 5 if all_tags.issubset(NON_TAXABLE_GRIDS) else 6
            else:
                # If no export data is available, fetch it from fiskaly
                if not tax.company_id.l10n_de_vat_export_data:
                    tax.company_id.l10n_de_update_vat_export_data()

                # Sort to prioritize standard VATs (lower IDs) over historical ones (higher IDs) when selecting the export ID
                sorted_vats = sorted(tax.company_id.l10n_de_vat_export_data, key=lambda x: x['vat_definition_export_id'])
                definition_export_id = next((i['vat_definition_export_id'] for i in sorted_vats if i['percentage'] == tax.amount), 0)

                # For special circumstances we have to create a new VAT definition with ID above 1000
                if not definition_export_id:
                    vat_definition_export_id = tax.amount + 1000
                    new_vat_response = self.company_id._l10n_de_fiskaly_dsfinvk_rpc('PUT', f'/vat_definitions/{vat_definition_export_id}', {"percentage": tax.amount})
                    if new_vat_response.status_code == 200:
                        definition_export_id = new_vat_response.json().get("vat_definition_export_id", 0)
                        tax.company_id.l10n_de_update_vat_export_data()
                tax.l10n_de_vat_definition_export_identifier = definition_export_id
