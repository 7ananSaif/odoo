from odoo import api, fields, models
from dateutil.relativedelta import relativedelta


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_in_fetch_vendor_edi_feature_enabled = fields.Boolean(related='company_id.l10n_in_fetch_vendor_edi_feature')

    # enet_batch_payment related fields
    bank_template_id = fields.Many2one('enet.bank.template', string='Bank Template')
    has_enet_payment_method = fields.Boolean(compute='_compute_has_enet_payment_method')
    l10n_in_enet_vendor_batch_payment_feature_enabled = fields.Boolean(related='company_id.l10n_in_enet_vendor_batch_payment_feature')

    @api.depends('outbound_payment_method_line_ids.payment_method_id.code')
    def _compute_has_enet_payment_method(self):
        for journal in self:
            if journal.company_id.l10n_in_enet_vendor_batch_payment_feature:
                journal.has_enet_payment_method = any(
                    payment_method.payment_method_id.code in ['enet_rtgs', 'enet_neft', 'enet_fund_transfer', 'enet_demand_draft']
                    for payment_method in journal.outbound_payment_method_line_ids
                )
            else:
                journal.has_enet_payment_method = False

    def l10n_in_action_fetch_irn_data_for_account_journal(self):
        """Fetch Vendor Bills:
        - If previous month's return has failed `missing_fetch_einvoice` check → fetch for previous month.
        - Also current month's return exists → fetch for current month.
        """

        def _find_return(date_from, date_to, extra_domain=None):
            domain = [
                ('date_from', '=', date_from),
                ('date_to', '=', date_to),
                ('company_id', '=', self.company_id.id),
                ('type_id', '=', gstr2b_return_type.id),
            ]
            if extra_domain:
                domain += extra_domain
            return self.env['account.return'].search(domain, limit=1)

        if not self.company_id.account_opening_date:
            return self.env['account.return'].action_open_tax_return_view()

        gstr2b_return_type = self.env.ref('l10n_in_reports.in_gstr2b_return_type', raise_if_not_found=False)
        if not gstr2b_return_type:
            return

        today = fields.Date.today()

        # Previous month return
        prev_return = _find_return(
            today + relativedelta(months=-1, day=1),
            today + relativedelta(months=-1, day=31),
            extra_domain=[('is_completed', '=', False)]
        )
        if prev_return:
            prev_return.refresh_checks()
            if prev_return.check_ids.filtered(lambda c: c.code == 'missing_fetch_einvoice' and c.result == 'failure'):
                prev_return.action_l10n_in_get_irn_data()

        curr_return = _find_return(today + relativedelta(day=1), today + relativedelta(day=31))
        if curr_return:
            return curr_return.action_l10n_in_get_irn_data()
