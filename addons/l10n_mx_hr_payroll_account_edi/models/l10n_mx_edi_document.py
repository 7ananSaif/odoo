# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class L10nMxEdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    payslip_id = fields.Many2one('hr.payslip')

    state = fields.Selection(
        selection_add=[
            ('payslip_sent', "Sent"),
            ('payslip_sent_failed', "Send In Error"),
            ('payslip_cancel', "Cancel"),
            ('payslip_cancel_failed', "Cancel In Error")],
        ondelete={
            'payslip_sent': 'cascade',
            'payslip_sent_failed': 'cascade',
            'payslip_cancel': 'cascade',
            'payslip_cancel_failed': 'cascade'})

    @api.model
    def _create_update_payslip_document(self, payslip, document_values):
        """ Create/update a new document for payslip.

        :param payslip:         A payslip.
        :param document_values: The values to create the document.
        """
        # Never remove a document already recorded in the SAT system.
        remaining_documents = payslip.l10n_mx_edi_document_ids.filtered(
            lambda doc: doc.sat_state not in ('valid', 'cancelled', 'skip'))

        if document_values['state'] in ('payslip_sent', 'payslip_cancel'):
            accept_method_state = f"{document_values['state']}_failed"
        else:
            accept_method_state = document_values['state']

        document = remaining_documents._create_update_document(
            payslip, document_values, lambda x: x.state == accept_method_state)

        document_states_to_remove = {'payslip_sent_failed', 'payslip_cancel_failed'}
        remaining_documents.filtered(lambda x: x != document and x.state in document_states_to_remove).unlink()

        if document.state in ('payslip_sent', 'payslip_cancel'):
            remaining_documents.exists().filtered(
                lambda x: x != document and x.attachment_uuid == document.attachment_uuid).write({'sat_state': 'skip'})

        return document
