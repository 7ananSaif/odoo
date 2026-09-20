# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class HrPayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    def _adapt_records_to_w3(self, debit_credit='debit'):
        ''' A special case in some contracts needs to be reported in another section of the tax report.
            We need to remove the reporting to W1 and change the reporting from W2 to W3 for those case.
        '''
        if not self:
            return
        w3_tag = self.env.ref('l10n_au.account_tax_report_payg_w3_tag')._get_matching_tags()
        w2_tag = self.env.ref('l10n_au.account_tax_report_payg_w2_tag')._get_matching_tags()
        w1_tag = self.env.ref('l10n_au.account_tax_report_payg_w1_tag')._get_matching_tags()
        for record in self:
            tag_ids = []
            tags_list = record.salary_rule_id.debit_tag_ids if debit_credit == 'debit' else record.salary_rule_id.credit_tag_ids
            for tag in tags_list:
                if tag == w2_tag:
                    tag_ids += [w3_tag.id]
                elif tag == w1_tag:
                    continue
                else:
                    tag_ids += [tag.id]
            if debit_credit == 'debit':
                record.debit_tag_ids = tag_ids
            else:
                record.credit_tag_ids = tag_ids

    @api.depends('salary_rule_id.debit_tag_ids', 'version_id.l10n_au_report_to_w3')
    def _compute_debit_tags(self):
        lines_to_report_in_w3 = self.filtered(lambda record: record.version_id.l10n_au_report_to_w3)
        lines_to_report_in_w3._adapt_records_to_w3('debit')
        super(HrPayslipLine, self - lines_to_report_in_w3)._compute_debit_tags()

    @api.depends('salary_rule_id.credit_tag_ids', 'version_id.l10n_au_report_to_w3')
    def _compute_credit_tags(self):
        lines_to_report_in_w3 = self.filtered(lambda record: record.version_id.l10n_au_report_to_w3)
        lines_to_report_in_w3._adapt_records_to_w3('credit')
        super(HrPayslipLine, self - lines_to_report_in_w3)._compute_credit_tags()
