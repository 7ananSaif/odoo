from odoo import models, _


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _l10n_es_get_report_modelo_number(self):
        self.ensure_one()
        xmlid_to_modelo = {
            "l10n_es_reports.es_mod303_tax_return_type": 303,
        }
        return xmlid_to_modelo.get(self.type_external_id, None)

    def _get_vat_closing_entry_additional_domain(self):
        # EXTENDS account_reports
        domain = super()._get_vat_closing_entry_additional_domain()
        mod_number = self._l10n_es_get_report_modelo_number()
        if mod_number in (111, 115, 303):
            mod_tags = self.env.ref(f'l10n_es.mod_{mod_number}').line_ids.expression_ids._get_matching_tags()
            domain.append(('tax_tag_ids', 'in', mod_tags.ids))
        return domain

    def action_validate(self, bypass_failing_tests=False):
        self.ensure_one()
        self._review_checks(bypass_failing_tests)

        mod_number = self._l10n_es_get_report_modelo_number()
        if mod_number:
            wiz_name = f'l10n_es_reports.aeat.boe.mod{mod_number}.export.wizard'
            options = self._get_closing_report_options()
            options['l10n_es_reports_boe_wizard_id'] = self.id
            # We can't use .create() here because mod390 has required fields,
            # leading to Validation Error in this specific situation.
            # In master this was solved by moving the 'required' on the xml declaration of the field.
            return {
                'type': 'ir.actions.act_window',
                'name': _('Complete the BOE fields'),
                'res_model': wiz_name,
                'view_mode': 'form',
                'target': 'new',
                'views': [(self.env.ref(f'l10n_es_reports.mod{mod_number}_boe_wizard').id, 'form')],
                'context': {
                    **self.env.context,
                    'dialog_size': 'medium',
                    'l10n_es_reports_report_options': options,
                    'proceed_with_locking': True,
                    'return_id': self.id,
                    'default_report_id': self.type_id.report_id.id,
                    'default_use_proceed_with_locking': True,
                },

            }
        return super().action_validate(bypass_failing_tests)
