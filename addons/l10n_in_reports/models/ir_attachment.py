# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from odoo.exceptions import ValidationError, UserError


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.ondelete(at_uninstall=False)
    def _unlink_except_payorder_file(self):
        for attachment in self:
            if attachment.res_model != 'account.batch.payment' or attachment.company_id.country_code != 'IN':
                continue
            batch = self.env['account.batch.payment'].browse(attachment.res_id)
            if batch and attachment.id in batch.l10n_in_pay_order_attachment_ids.ids:
                raise ValidationError(_("You cannot delete a Pay Order once it has been generated."))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_government_attachment(self):
        """
        Prevents the deletion of attachments related to government-issued documents.
        """
        for attachment in self.filtered(lambda a: a.res_model == 'account.move' and a.mimetype == 'application/json'):
            irn_number = attachment.name.split('.')[0]
            moves = self.env['account.move'].search([('l10n_in_irn_number', 'like', irn_number)])
            if moves:
                raise UserError(_("You can't unlink an attachment that you received from the government"))
