from ast import literal_eval

from odoo import fields, models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    # Field to annotate the date for account reports.
    # This is set by passing a default in the context when opening the wizard from a message.
    account_reports_annotation_date = fields.Date("Annotated For")

    def _prepare_schedule_message_post_values(self, post_values):
        return {
            **super()._prepare_schedule_message_post_values(post_values),
            'account_reports_annotation_date': self.account_reports_annotation_date,
        }

    def _action_send_mail_comment(self, res_ids):
        # Getting the date before the super call as the orm cache is invalidated afterwards.
        account_reports_annotation_date = self.account_reports_annotation_date
        messages = super()._action_send_mail_comment(res_ids)
        if account_reports_annotation_date:
            self.env['account.report.annotation'].sudo().create([
                {'message_id': msg.id, 'date': account_reports_annotation_date}
                for msg in messages
            ])
        return messages

    def _action_send_mail(self, auto_commit=False):
        # Getting the date before the super call as the orm cache is invalidated afterwards.
        account_reports_annotation_date = self.account_reports_annotation_date
        mails, messages = super()._action_send_mail(auto_commit=auto_commit)
        if account_reports_annotation_date:
            self.env['account.report.annotation'].sudo().create([
                {'message_id': msg.id, 'date': account_reports_annotation_date}
                for msg in messages
            ])
        return mails, messages

    def action_send_mail(self):
        if self.model != 'account.return':
            return super().action_send_mail()

        return_id = self.env['account.return'].browse(literal_eval(self.res_ids))
        return_id._action_finalize_payment()
        super().action_send_mail()
        return {
            'type': 'ir.actions.client',
            'tag': 'action_return_refresh',
            'params': {
                'next_action': {'type': 'ir.actions.act_window_close'},
                'return_ids': return_id.ids,
            },
        }
