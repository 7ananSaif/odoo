# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _to_store(self, store, fields, **kwargs):
        def super_to_store(records, fields):
            super_records = super(IrAttachment, records)
            if hasattr(super_records, '_to_store'):
                super_records._to_store(store, fields, **kwargs)
            else:
                assert not kwargs
                store.add_records_fields(records, fields)

        if not self.env.user._is_portal() or 'access_token' in fields:
            super_to_store(self, fields)
            return

        article_thread_ids = set(
            self.env['knowledge.article.thread'].sudo(False).with_user(self.env.user)
            .browse(
                self.filtered(lambda attachment: attachment.res_model == 'knowledge.article.thread')
                .mapped('res_id')
            )
            .filtered(lambda thread: thread.has_access('read'))
            .ids
        )
        attachments_with_token  = self.filtered(
            lambda attachment:
                attachment.res_model == 'knowledge.article.thread'
                and attachment.res_id in article_thread_ids
        )
        super_to_store(self - attachments_with_token, fields)
        # Add access_token to the knowledge article's attachments for portal users
        fields = fields + store._format_fields(attachments_with_token, ['access_token'])
        super_to_store(attachments_with_token, fields)
