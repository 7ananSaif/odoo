from datetime import timedelta

from odoo import api, fields, models


class AccountReportAsyncExport(models.Model):
    _name = 'account.report.async.export'
    _description = "Account Report Async Export"

    name = fields.Char()
    date_from = fields.Date()
    date_to = fields.Date()
    report_id = fields.Many2one('account.report')
    recipient = fields.Selection([
        ("DGI_EDI_TVA", "DGFiP"),
        ("CEC_EDI_TVA", "Expert Accountant"),
        ("OGA_EDI_TVA", "OGA"),
    ], readonly=True)
    document_ids = fields.One2many(comodel_name='account.report.async.document', inverse_name='account_report_async_export_id')
    state = fields.Selection(
        selection=[
            ('to_send', "To send"),
            ('sent', "Sent"),
            ('accepted', "Accepted"),
            ('rejected', "Rejected"),
            ('mixed', "Mixed"),
        ], default='to_send', compute='_compute_state', store=True)

    @api.depends('document_ids.state')
    def _compute_state(self):
        for record in self:
            states = set(record.document_ids.mapped('state'))
            if not states or states == {'to_send'}:
                record.state = 'to_send'
            elif len(states) == 1:
                record.state = states.pop()
            else:
                record.state = 'mixed'

    @api.model
    def _cron_process_all_reports_async_export(self):
        async_exports = self.search([('document_ids.state', 'in', ('to_send', 'sent'))])
        async_exports.document_ids._process_reports_async_documents()

        # Trigger the CRON again if there are remainineg jobs to process
        if async_exports.filtered(lambda export: export.document_ids.filtered(lambda document: document.state in ('to_send', 'sent'))):
            self.env.ref('l10n_fr_reports.ir_cron_l10n_fr_reports')._trigger(fields.Datetime.now() + timedelta(minutes=30))

    # ------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------

    def button_process_report(self):
        self.env.ref('l10n_fr_reports.ir_cron_l10n_fr_reports').method_direct_trigger()
