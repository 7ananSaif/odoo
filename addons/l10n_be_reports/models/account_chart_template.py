# -*- coding: utf-8 -*-
from odoo.addons.account.models.chart_template import template
from odoo import _, models
from odoo.fields import Command


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('be_asso', 'res.company')
    def _get_be_asso_reports_res_company(self):
        return self._get_be_reports_res_company()

    @template('be_comp', 'res.company')
    def _get_be_comp_reports_res_company(self):
        return self._get_be_reports_res_company()

    @template('be', 'res.company')
    def _get_be_reports_res_company(self):
        return {
            self.env.company.id: {
                'deferred_expense_account_id': 'a490',
                'deferred_revenue_account_id': 'a493',
            }
        }

    @template('be_asso', 'res.partner')
    def _get_be_asso_reports_res_partner(self):
        return self._get_be_reports_res_partner()

    @template('be_comp', 'res.partner')
    def _get_be_comp_reports_res_partner(self):
        return self._get_be_reports_res_partner()

    @template('be', model='res.partner')
    def _get_be_reports_res_partner(self):
        return {
            'l10n_be_reports.partner_fps_belgium': {
                'property_account_receivable_id': 'a4112',
                'property_account_payable_id': 'a4512',
            },
            'l10n_be_reports.partner_centre_de_perception_belgium': {
                'property_account_receivable_id': 'a4121',
                'property_account_payable_id': 'a4521',
            },
        }

    @template(model='account.reconcile.model')
    def _get_be_account_reconcile_model(self, template_code):
        be_recon_models = {}
        if template_code in ['be', 'be_comp', 'be_asso']:
            prepayment_communication = self.env['qr.code.payment.wizard']._be_company_vat_communication(self.env.company).replace('+++', '')
            prepayment_collection_partner = self.env.ref('l10n_be_reports.partner_centre_de_perception_belgium', raise_if_not_found=False)
            be_recon_models = {
                'advanced_tax_payment_reco': {
                    'name': _('Advanced Tax Payment'),
                    'trigger': 'auto_reconcile' if prepayment_communication else 'manual',
                    'match_partner_ids': [prepayment_collection_partner.id] if prepayment_collection_partner else [],
                    'match_amount': 'lower',
                    'match_amount_max': 0.0,
                    **({
                        'match_label': 'contains',
                        'match_label_param': prepayment_communication,
                    } if prepayment_communication else {}),
                    'line_ids': [
                        Command.create({
                            'partner_id': prepayment_collection_partner.id if prepayment_collection_partner else False,
                            'account_id': 'a4121',
                            'amount_type': 'percentage',
                            'amount_string': '100',
                        }),
                    ],
                },
            }
        return be_recon_models
