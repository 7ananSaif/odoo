# -*- coding: utf-8 -*-
from odoo import models, api

from werkzeug.urls import url_encode
from collections import defaultdict


class SignRequest(models.Model):
    _name = 'sign.request'
    _inherit = ['sign.request', 'documents.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        sign_requests = super().create(vals_list)
        attachment_ids = sign_requests.template_id.document_ids.attachment_id.ids
        documents = self.env['documents.document'].search([('attachment_id', 'in', attachment_ids)])
        attachment_docs = defaultdict(list)
        for doc in documents:
            attachment_docs[doc.attachment_id.id].append(doc)

        for sr in sign_requests:
            if sr.template_id.folder_id and not sr.reference_doc:
                document_ids = []
                for attachment in sr.template_id.document_ids.attachment_id:
                    document_ids += attachment_docs[attachment.id]
                if len(document_ids) == 1:
                    sr.reference_doc = f"documents.document,{document_ids[0].id}"
                elif document_ids and all(doc.folder_id == document_ids[0].folder_id for doc in document_ids):
                    sr.reference_doc = f"documents.document,{document_ids[0].folder_id.id}"
        return sign_requests

    def _get_linked_record_action(self, default_action=None):
        self.ensure_one()
        if self.reference_doc._name == 'documents.document':
            url_params = url_encode({
                'preview_id': self.reference_doc.id,
                'view_id': self.env.ref("documents.document_view_kanban").id,
                'menu_id': self.env.ref("documents.menu_root").id,
                'folder_id': self.reference_doc.folder_id.id,
            })
            return {
                'type': 'ir.actions.act_url',
                'url': f"/odoo/action-documents.document_action_preference?{url_params}",
                'target': 'self',
            }
        else:
            return super()._get_linked_record_action(default_action=default_action)

    def _generate_completed_documents(self):
        """ Ensure document are created by the super method which only create the related attachment. """
        super(SignRequest, self.with_context(no_document=False))._generate_completed_documents()

    def _send_completed_documents(self):
        """ Ensure no documents are created when sending the completed document.

        The super method call _generate_completed_documents which create the completed document then the attachments
        of the completed documents are sent by mail, and we want to avoid to turn those attachments again into
        document by forcing no_document=True (otherwise the system will attempt to create a document on attachment
        already referenced by a document leading to a duplicate key constraint violation).
        """
        super(SignRequest, self.with_context(no_document=True))._send_completed_documents()

    def _get_document_tags(self):
        return self.template_id.documents_tag_ids

    def _get_document_folder(self):
        return self.template_id.folder_id


class SignRequestItem(models.Model):
    _inherit = 'sign.request.item'

    def _sign(self, signature, **kwargs):
        """ Give view access to the signer on the completed documents.

        Note that this function is always called in sudo (see super method).
        """
        super()._sign(signature, **kwargs)
        completed_documents_sudo = self.env['documents.document'].search([
            ('attachment_id', 'in', self.sign_request_id.completed_document_attachment_ids.ids)
        ])
        # Add view permission to the signer if he has not already inherited a larger permission from the folder
        if not completed_documents_sudo.access_ids.filtered(
                lambda access: access.partner_id == self.partner_id and access.role == 'edit'):
            completed_documents_sudo.action_update_access_rights(partners={self.partner_id: ('view', False)})

        completed_documents_sudo.partner_id = self.partner_id
