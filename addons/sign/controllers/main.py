# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import io
import zipfile
import logging
import mimetypes


from odoo import http, tools, Command, _, fields
from odoo.http import request, content_disposition
from odoo.tools import consteq, format_date, posix_to_ldml
from odoo.tools.pdf import PdfFileWriter, PdfFileReader
from odoo.tools.misc import babel_locale_parse
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError

_logger = logging.getLogger()


class Sign(http.Controller):

    def get_document_qweb_context(self, sign_request_id, token, **post):
        result = {}
        sign_request = http.request.env['sign.request'].sudo().browse(sign_request_id).exists()
        if not sign_request:
            result.update(error=True, template='sign.deleted_sign_request')
            return result
        current_request_item = sign_request.request_item_ids.filtered(lambda r: consteq(r.access_token, token))
        if not current_request_item and sign_request.access_token != token:
            result.update(error=True)
            return result
        if current_request_item and current_request_item.partner_id.lang:
            http.request.update_context(lang=current_request_item.partner_id.lang)

        # This context is needed since we want to show in the sidebar only non
        # archive fields but we want to be able to still use archived fields
        # in the documents to avoid breaking existing sign requests and templates.
        sign_item_types = http.request.env['sign.item.type'].with_context(active_test=False).sudo().search_read([])
        if not sign_item_types:
            raise UserError(_("Unable to sign the document due to missing required data. Please contact an administrator."))

        # Currently only Signature, Initials, Text are allowed to be added while signing
        item_type_signature = request.env.ref('sign.sign_item_type_signature', raise_if_not_found=False)
        item_type_initial = request.env.ref('sign.sign_item_type_initial', raise_if_not_found=False)
        item_type_text = request.env.ref('sign.sign_item_type_text', raise_if_not_found=False)
        edit_while_signing_allowed_type_ids = {
            item_type_signature and item_type_signature.id,
            item_type_initial and item_type_initial.id,
            item_type_text and item_type_text.id,
        }
        for item_type in sign_item_types:
            item_type['edit_while_signing_allowed'] = item_type['id'] in edit_while_signing_allowed_type_ids

        if current_request_item:
            for item_type in sign_item_types:
                if item_type['auto_field']:
                    item_type['auto_value'] = current_request_item._get_auto_field_value(item_type)
                if item_type['item_type'] in ['signature', 'initial']:
                    signature_field_name = 'sign_signature' if item_type['item_type'] == 'signature' else 'sign_initials'
                    user_signature = current_request_item._get_user_signature(signature_field_name)
                    user_signature_frame = current_request_item._get_user_signature_frame(signature_field_name+'_frame')
                    item_type['auto_value'] = 'data:image/png;base64,%s' % user_signature.decode() if user_signature else False
                    item_type['frame_value'] = 'data:image/png;base64,%s' % user_signature_frame.decode() if user_signature_frame else False

            if current_request_item.state == 'sent':
                """ When signer attempts to sign the request again,
                its localisation should be reset.
                We prefer having no/approximative (from geoip) information
                than having wrong old information (from geoip/browser)
                on the signer localisation.
                """
                current_request_item.write({
                    'latitude': request.geoip.location.latitude or 0.0,
                    'longitude': request.geoip.location.longitude or 0.0,
                })

        item_values = {}
        frame_values = {}
        sr_values = http.request.env['sign.request.item.value'].sudo().search([('sign_request_id', '=', sign_request.id), '|', ('sign_request_item_id', '=', current_request_item.id), ('sign_request_item_id.state', '=', 'completed')])
        for value in sr_values:
            item_values[value.sign_item_id.id] = value.value
            frame_values[value.sign_item_id.id] = value.frame_value

        if sign_request.state != 'shared':
            request.env['sign.log'].sudo().create({
                'sign_request_id': sign_request.id,
                'sign_request_item_id': current_request_item.id,
                'action': 'open',
            })

        lang_code = sign_request.communication_company_id.partner_id.lang
        lang = request.env['res.lang']._lang_get(lang_code)
        locale = babel_locale_parse(lang_code)
        date_format = ""
        if lang:
            date_format = posix_to_ldml(lang.date_format, locale=locale)
        portal = post.get('portal')

        result['rendering_context'] = {
            'sign_request': sign_request,
            'current_request_item': current_request_item,
            'state_to_sign_request_items_map': dict(tools.groupby(sign_request.request_item_ids, lambda sri: sri.state)),
            'token': token,
            'nbComments': len(sign_request.message_ids.filtered(lambda m: m.message_type == 'comment')),
            'hasItems': len(sign_request.template_id.sign_item_ids) > 0,
            'sign_items': sign_request.template_id.sign_item_ids,
            'item_values': item_values,
            'frame_values': frame_values,
            'frame_hash': current_request_item.frame_hash if current_request_item else '',
            'role': current_request_item.role_id.id if current_request_item else 0,
            'role_name': current_request_item.role_id.name if current_request_item else '',
            'readonly': not (current_request_item and current_request_item.state == 'sent' and sign_request.state in ['sent', 'shared']),
            'sign_item_types': sign_item_types,
            'sign_item_select_options': sign_request.template_id.sign_item_ids.mapped('option_ids'),
            'portal': portal,
            'company_id': (sign_request.communication_company_id or sign_request.create_uid.company_id).id,
            'today_formatted_date': format_date(http.request.env, fields.Date.today(), lang_code=lang_code),
            'date_format': date_format.lower(),
            'show_thank_you_dialog': bool(sign_request.completed_document_attachment_ids) and not portal,
        }
        return result

    # -------------
    #  HTTP Routes
    # -------------

    @http.route(['/sign/<share_link>'], type='http', auth='public')
    def share_link(self, share_link, **post):
        """
        This controller is used for retro-compatibility of old shared links. share_link was a token saved on the
        template. We map them to the shared sign request created during upgrade and redirect to the correct URL.
        :param share_link: share
        :return: redirect to the sign_document_from_mail controller
        """
        sign_request_item = request.env['sign.request.item'].sudo().search([('access_token', '=', share_link)], limit=1)
        if not sign_request_item or sign_request_item.sign_request_id.state != 'shared':
            return request.not_found()
        return request.redirect('/sign/document/mail/%s/%s' % (sign_request_item.sign_request_id.id, sign_request_item.access_token))

    @http.route(["/sign/document/mail/<int:request_id>/<token>"], type='http', auth='public', website=True)
    def sign_document_from_mail(self, request_id, token, **post):
        sign_request = request.env['sign.request'].sudo().browse(request_id).exists()
        if not sign_request or sign_request.validity and sign_request.validity < fields.Date.today():
            return http.request.render('sign.deleted_sign_request', status=404)
        current_request_item = sign_request.request_item_ids.filtered(lambda r: consteq(r.access_token, token))
        if not current_request_item:
            return http.request.render('sign.deleted_sign_request', status=404)
        # The sign request should be evaluated but the timestamp has been removed from the parameter.
        # In that case, we don't render the sign_request_expired template
        removed_timestamp_arg = sign_request.state == 'sent' and (not post.get('timestamp') or not post.get('exp'))
        if sign_request.state != 'shared' and not current_request_item._validate_expiry(post.get('timestamp'), post.get('exp')):
            if removed_timestamp_arg:
                return http.request.render('sign.deleted_sign_request', status=404)
            return request.render('sign.sign_request_expired', {'resend_expired_link': '/sign/resend_expired_link/%s/%s' % (request_id, token)}, status=403)

        current_request_item.access_via_link = True

        if http.request.params.get('refuseDocument'):
            return request.redirect('/sign/document/%s/%s?refuse_document=1' % (request_id, token))
        return request.redirect('/sign/document/%s/%s' % (request_id, token))

    @http.route(["/sign/document/<int:sign_request_id>/<token>"], type='http', auth='public', website=True)
    def sign_document_public(self, sign_request_id, token, **post):
        res = self.get_document_qweb_context(sign_request_id, token, **post)
        if res.get('error'):
            return request.render(res['template']) if res.get('template') else request.not_found()

        return http.request.render('sign.doc_sign', res.get('rendering_context'))

    @http.route([
        '/sign/download/<int:request_id>/<token>/<download_type>',
        '/sign/download/<int:request_id>/<token>/<download_type>/<int:sign_document_id>'
    ], type='http', auth='public')
    def download_document(self, request_id, token, download_type, sign_document_id=None, **post):
        """Handles document download requests for sign requests.

        This method routes requests to download different types of documents
        (log, origin, or completed) associated with a sign request. It validates
        the request and delegates to specific handlers based on the download type.
        Args:
            request_id (int): The ID of the sign request.
            token (str): The access token for the sign request.
            download_type (str): Type of document to download ('log', 'origin', or 'completed').
            sign_document_id (int, optional): Specific document ID for 'origin' download type.
            **post: Additional POST parameters (not used in this method).
        Returns:
            http.Response: Response containing the requested document or a redirect/not found response.
        """
        sign_request = self._get_sign_request(request_id, token)
        if not sign_request:
            return request.not_found()

        if download_type == "log":
            return self._handle_log_download(sign_request)
        elif download_type == "origin":
            return self._handle_origin_download(sign_request, sign_document_id)
        elif download_type == "completed":
            return self._handle_completed_download(sign_request, sign_document_id)

        return self._redirect_to_sign_document(sign_request)

    def _get_sign_request(self, request_id, token):
        sign_request = request.env['sign.request'].sudo().browse(request_id).exists()
        return sign_request if sign_request and consteq(sign_request.access_token, token) else None

    def _handle_log_download(self, sign_request):
        """Generates and returns a PDF log (certificate) for the sign request.
        Renders a QWeb report as a PDF containing the sign request's log details.
        Args:
            sign_request (odoo.models.Model): The sign request record.
        Returns:
            http.Response: Response containing the PDF content with appropriate headers.
        """
        report_action = request.env['ir.actions.report'].sudo()
        pdf_content, _dummy = report_action._render_qweb_pdf(
            'sign.action_sign_request_print_logs',
            sign_request.id,
            data={
                'format_date': tools.format_date,
                'company_id': sign_request.communication_company_id,
            }
        )
        return request.make_response(pdf_content, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf_content)),
            ('Content-Disposition', 'attachment; filename=Certificate.pdf;'),
        ])

    def _handle_origin_download(self, sign_request, sign_document_id):
        """Handles the download of the original (unsigned) document for a sign request.

        Retrieves the original document based on either a specific document ID or
        the documents associated with the sign request's template. If multiple documents
        exist and no specific ID is provided, returns a ZIP file containing all documents.

        Args:
            sign_request (odoo.models.Model): The sign request record.
            sign_document_id (int, optional): The ID of the specific document to download.

        Returns:
            http.Response: Response containing the document data or a ZIP file, or a 404 response if not found.
        """
        if sign_document_id:
            document_id = request.env['sign.document'].sudo().browse(sign_document_id)
            if not document_id:
                return request.not_found()
            attachment_data = document_id.attachment_id.datas
            return self._create_document_response(sign_request, attachment_data, document_name=document_id.name)

        template_documents_ids = sign_request.template_document_ids
        if len(template_documents_ids) == 1:
            attachment_data = template_documents_ids[0].attachment_id.datas
            return self._create_document_response(sign_request, attachment_data, document_name=template_documents_ids[0].name)

        # If there are multiple documents and no specific ID was provided, create a ZIP
        if len(template_documents_ids) > 1:
            return self._create_zip_response([sign_request])

        return request.not_found()

    def _handle_completed_download(self, sign_request, sign_document_id=None):
        """Handles the download of completed (signed) documents for a sign request.

        Generates completed documents if they don't exist, then returns either a single
        document response or a ZIP file containing multiple documents based on the number
        of completed documents.
        Args:
            sign_request (odoo.models.Model): The sign request record.
            sign_document_id (int, optional): The ID of the specific completed document to download.
        Returns:
            http.Response: Response containing either a single document or a ZIP file.
        """
        if not sign_request.completed_document_ids and sign_request.state == 'signed':
            sign_request.sudo()._generate_completed_documents()

        if sign_document_id:
            completed_document = sign_request.completed_document_ids.filtered(lambda d: d.id == sign_document_id)
            if completed_document:
                return self._create_document_response(sign_request, completed_document.file, document_name=completed_document.document_id.name)
            return request.not_found()

        if len(sign_request.completed_document_ids) == 1:
            return self._create_document_response(sign_request, sign_request.completed_document_ids[0].file, document_name=sign_request.completed_document_ids[0].document_id.name)

        return self._create_zip_response([sign_request])

    def _create_zip_response(self, sign_requests):
        """Creates a ZIP file containing multiple documents for sign requests.
        Args:
            sign_requests (odoo.models.Model): The sign request record(s).
        Returns:
            http.Response: Response containing the ZIP file with appropriate headers.
        """
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zipfile_obj:
            for sign_request in sign_requests:
                document_type = 'completed' if sign_request.state == 'signed' else 'origin'
                existing_document_names = set()
                if document_type == 'completed':
                    documents = sign_request.completed_document_ids
                    for doc in documents:
                        download_name = self._format_document_name(sign_request, doc.document_id.name, existing_document_names)
                        zipfile_obj.writestr(download_name, base64.b64decode(doc.file))
                elif document_type == 'origin':
                    documents = sign_request.template_document_ids
                    for doc in documents:
                        download_name = self._format_document_name(sign_request, doc.name, existing_document_names)
                        zipfile_obj.writestr(download_name, base64.b64decode(doc.attachment_id.datas))

        content = buffer.getvalue()
        filename = 'sign_request_documents.zip'
        return request.make_response(content, headers=[
            ('Content-Disposition', content_disposition(filename)),
            ('Content-Type', 'application/zip'),
            ('Content-Length', len(content))
        ])

    def _format_document_name(self, sign_request, doc_name, existing_document_names):
        """Formats a document name for download, handling PDF extensions and duplicates.
        Args:
            sign_request (odoo.models.Model): The sign request record.
            doc_name (str): The original document name.
            existing_document_names (set): Set of existing document names to check for duplicates.
        Returns:
            str: The formatted document name.
        """
        subject = sign_request.subject or request.env._("Documents of Request %s", str(sign_request.id))
        if subject.endswith('.pdf'):
            subject = subject[:-4]
        if not doc_name.endswith('.pdf'):
            doc_name += '.pdf'
        download_name = f'{subject}/{doc_name}'
        counter = 1
        while download_name in existing_document_names:
            name, ext = download_name.rsplit('.', 1)
            download_name = f'{name} ({counter}).{ext}'
            counter += 1
        existing_document_names.add(download_name)
        return download_name

    def _create_document_response(self, sign_request, attachment_data, document_name=None):
        """Creates an HTTP response for a single document download.
        Determines the file extension and MIME type based on the sign request's template and returns a response with
        the decoded document data and appropriate headers.
        Args:
            sign_request (odoo.models.Model): The sign request object.
            attachment_data (str): Base64-encoded document data.
            document_name (str, optional): Specific name for the document, if provided.
        Returns:
            http.Response: Response containing the decoded document with appropriate headers.
        """
        extension = '.' + sign_request.template_id.document_ids[0].attachment_id.mimetype.replace('application/', '').replace(';base64', '')

        if document_name:
            # Use the provided document name if available
            if document_name.endswith(extension):
                filename = document_name
            else:
                filename = document_name + extension
        else:
            # Fall back to the reference name
            filename = sign_request.reference.replace(extension, '') + extension

        return request.make_response(
            base64.b64decode(attachment_data),
            headers=[
                ('Content-Type', mimetypes.guess_type(filename)[0] or 'application/octet-stream'),
                ('Content-Disposition', content_disposition(filename))
            ]
        )

    def _redirect_to_sign_document(self, sign_request):
        return request.redirect(f"/sign/document/{sign_request.id}/{sign_request.access_token}")

    @http.route(['/sign/download/zip/<ids>'], type='http', auth='user')
    def download_multiple_documents(self, ids, **post):
        """ If the user has access to all the requests, create a zip archive of all the documents requested and
        return it.
        The document each are in a folder named by their request ID to ensure unicity of files.
        """
        if not request.env.user.has_group('sign.group_sign_user'):
            return request.render(
                'http_routing.http_error',
                {'status_code': _('Oops'),
                'status_message': _('You do not have access to these documents, please contact a Sign Administrator.')})

        sign_requests = http.request.env['sign.request'].browse(int(i) for i in ids.split(',')).exists()
        return self._create_zip_response(sign_requests)

    @http.route(['/sign/resend_expired_link/<int:request_id>/<token>'], type='http', auth='public', website=True)
    def resend_expired_link(self, request_id, token):
        sign_request = request.env['sign.request'].sudo().browse(request_id)
        if not sign_request or sign_request.state in ('signed', 'canceled', 'refused'):
            return http.request.render('sign.deleted_sign_request')
        current_request_item = sign_request.request_item_ids.filtered(lambda r: consteq(r.access_token, token))

        if current_request_item.state != 'sent':
            return http.request.render('sign.deleted_sign_request')
        current_request_item.send_signature_accesses()


        return request.render('sign.sign_request_expired', {
            'state': 'sent',
            'resend_expired_link': '/sign/resend_expired_link/%s/%s' % (request_id, token),
            'email': current_request_item.signer_email,
        })

    # -------------
    #  JSON Routes
    # -------------
    @http.route(["/sign/get_document/<int:request_id>/<token>"], type='jsonrpc', auth='user')
    def get_document(self, request_id, token):
        res = self.get_document_qweb_context(request_id, token)
        if res.get('error'):
            return request.render(res['template']) if res.get('template') else request.not_found()
        render_ctx = res.get('rendering_context')
        return {
            'html': request.env['ir.qweb']._render('sign._doc_sign', render_ctx),
            'context': {
                'refusal_allowed': self._check_refusal_conditions(render_ctx),
                'sign_request_token': render_ctx['sign_request'].access_token,
            }
        }

    @http.route(["/sign/get_original_documents/<int:request_id>/<token>"], type="jsonrpc", auth="user")
    def get_original_documents(self, request_id, token):
        sign_request = self._get_sign_request(request_id, token)
        if not sign_request:
            return request.not_found()

        original_documents = [
            {
                'id': doc.id,
                'name': doc.name
            }
            for doc in sign_request.template_document_ids
        ]
        return {
            'original_documents': original_documents
        }

    @http.route(["/sign/get_completed_documents/<int:request_id>/<token>"], type="jsonrpc", auth="user")
    def get_completed_documents(self, request_id, token):
        sign_request = self._get_sign_request(request_id, token)
        if not sign_request:
            return request.not_found()

        if not sign_request.completed_document_ids and sign_request.state == 'signed':
            sign_request.sudo()._generate_completed_documents()

        completed_documents = [
            {
                'id': doc.id,
                'name': doc.document_id.name
            }
            for doc in sign_request.completed_document_ids
        ]
        return {'completed_documents': completed_documents}

    def _check_refusal_conditions(self, context):
        """
        Checks if refusal is allowed based on the states and partners of the current request item
        and the sign request.
        :return: Boolean indicating whether refusal is allowed.
        """
        current_request_item = context.get('current_request_item')
        sign_request = context.get('sign_request')
        if not current_request_item or not sign_request:
            return False

        are_both_in_sent_state = (
            current_request_item.state == 'sent' and sign_request.state == 'sent'
        )
        is_different_partner = (
            current_request_item.partner_id != current_request_item.create_uid.partner_id
        )
        return are_both_in_sent_state and is_different_partner

    @http.route(["/sign/update_user_signature"], type="jsonrpc", auth="user")
    def update_signature(self, sign_request_id, role, signature_type=None, datas=None, frame_datas=None):
        sign_request_item_sudo = http.request.env['sign.request.item'].sudo().search([('sign_request_id', '=', sign_request_id), ('role_id', '=', role)], limit=1)
        user = http.request.env.user
        allowed = sign_request_item_sudo.partner_id.id == user.partner_id.id
        if not allowed or signature_type not in ['sign_signature', 'sign_initials'] or not user:
            return False
        user[signature_type] = datas[datas.find(',') + 1:]
        user[signature_type+'_frame'] = frame_datas[frame_datas.find(',') + 1:] if frame_datas else False
        return True

    @http.route(['/sign/send_public/<int:request_id>/<token>'], type='jsonrpc', auth='public')
    def make_public_user(self, request_id, token, name=None, mail=None):
        sign_request = http.request.env['sign.request'].sudo().search([('id', '=', request_id), ('access_token', '=', token)])
        if not sign_request or len(sign_request.request_item_ids) != 1 or sign_request.request_item_ids.partner_id:
            return False

        partner = self.env['mail.thread'].sudo()._partner_find_from_emails_single([mail], no_create=False)

        new_sign_request_sudo = sign_request.with_user(sign_request.create_uid).with_context(no_sign_mail=True).sudo().copy({
            'reference': sign_request.reference.replace('-%s' % _("Shared"), ''),
            'request_item_ids': [Command.create({
                'partner_id': partner.id,
                'role_id': sign_request.request_item_ids[0].role_id.id,
            })],
            'state': 'sent',
        })
        return {"requestID": new_sign_request_sudo.id, "requestToken": new_sign_request_sudo.access_token, "accessToken": new_sign_request_sudo.request_item_ids[0].access_token}

    @http.route([
        '/sign/send-sms/<int:request_id>/<token>/<phone_number>',
        ], type='jsonrpc', auth='public')
    def send_sms(self, request_id, token, phone_number):
        request_item = http.request.env['sign.request.item'].sudo().search([('sign_request_id', '=', request_id), ('access_token', '=', token), ('state', '=', 'sent')], limit=1)
        if not request_item:
            return False
        if request_item.role_id.auth_method == 'sms':
            request_item.sms_number = phone_number
            try:
                request_item._send_sms()
            except iap_tools.InsufficientCreditError:
                _logger.warning('Unable to send SMS: no more credits')
                request_item.sign_request_id.activity_schedule(
                    'mail.mail_activity_data_todo',
                    note=_("%s couldn't sign the document due to an insufficient credit error.", request_item.partner_id.display_name),
                    user_id=request_item.sign_request_id.create_uid.id
                )
                return False
        return True

    def _validate_auth_method(self, request_item_sudo, sms_token=None, **kwargs):
        if request_item_sudo.role_id.auth_method == 'sms':
            has_sms_credits = request.env['iap.account'].sudo().get_credits('sms') > 0  # credits > 0 because the credit was already spent
            # if there are no sms credits, we still allow the user to sign it
            if not sms_token and not has_sms_credits:
                request_item_sudo.signed_without_extra_auth = True
                return {'success': True}
            if not sms_token or sms_token != request_item_sudo.sms_token:
                return {
                    'success': False,
                    'sms': True
                }
            request_item_sudo.sign_request_id._message_log(
                body=_('%(partner)s validated the signature by SMS with the phone number %(phone_number)s.', partner=request_item_sudo.partner_id.display_name, phone_number=request_item_sudo.sms_number)
            )
            return {'success': True}
        return {'success': False}

    @http.route([
        '/sign/sign/<int:sign_request_id>/<token>',
        '/sign/sign/<int:sign_request_id>/<token>/<sms_token>'
    ], type='jsonrpc', auth='public')
    def sign(self, sign_request_id, token, sms_token=False, signature=None, **kwargs):
        request_item_sudo = http.request.env['sign.request.item'].sudo().search([
            ('sign_request_id', '=', sign_request_id),
            ('access_token', '=', token),
            ('state', '=', 'sent')
        ], limit=1)

        if not request_item_sudo or request_item_sudo.sign_request_id.validity and request_item_sudo.sign_request_id.validity < fields.Date.today():
            return {'success': False}

        sign_request = request_item_sudo.sign_request_id
        company = sign_request.communication_company_id or sign_request.create_uid.company_id
        result = {'success': True, 'company_country_code': company.country_id.code}
        if request_item_sudo.role_id.auth_method:
            result = self._validate_auth_method(request_item_sudo, sms_token=sms_token, **kwargs)
            result['company_country_code'] = company.country_id.code
            if not result.get('success'):
                return result

        sign_user = request.env['res.users'].sudo().search([('partner_id', '=', request_item_sudo.partner_id.id)], limit=1)
        if sign_user:
            # sign as a known user
            context = {}
            if request.env.user != sign_user and not request.env.user._is_public():
                context.update(logged_user_id=request.env.user.id)
            request_item_sudo = request_item_sudo.with_context(context).with_user(sign_user).sudo()
        request_item_sudo.sign(signature, **kwargs)
        return result

    @http.route(['/sign/refuse/<int:sign_request_id>/<token>'], type='jsonrpc', auth='public')
    def refuse(self, sign_request_id, token, refusal_reason="", refusal_name="", refusal_email=""):
        request_item = request.env["sign.request.item"].sudo().search(
            [
                ("sign_request_id", "=", sign_request_id),
                ("access_token", "=", token),
                ("state", "=", "sent"),
            ],
            limit=1,
        )
        if not request_item:
            return False

        refuse_user = request.env['res.users'].sudo().search([('partner_id', '=', request_item.partner_id.id)], limit=1)
        if refuse_user:
            # refuse as a known user
            request_item = request_item.with_user(refuse_user).sudo()
            refuse_log = _("The signature has been canceled by %(partner)s (%(role)s)", partner=refuse_user.name, role=request_item.role_id.name)
            request_item.sign_request_id.message_post(body=refuse_log)
        else:
            request_item = request_item.sudo()
            refuse_log = _(
                "The signature has been canceled by %(partner)s with email (%(email)s)",
                partner=refusal_name,
                email=refusal_email,
            )
            request_item.sign_request_id.message_post(body=refuse_log)

        sign_request = request.env["sign.request"].sudo().search(
            [("id", "=", sign_request_id)],
            limit=1,
        )
        if sign_request.state in ['sent', 'shared']:
            request_item.with_context(default_sign_request_item_id=request_item.id)._refuse(
                sign_request.state,
                refusal_reason,
                refusal_name,
                refusal_email,
            )
        return True

    @http.route(['/sign/save_location/<int:request_id>/<token>'], type='jsonrpc', auth='public')
    def save_location(self, request_id, token, latitude=0, longitude=0):
        sign_request_item = http.request.env['sign.request.item'].sudo().search([('sign_request_id', '=', request_id), ('access_token', '=', token)], limit=1)
        sign_request_item.write({'latitude': latitude, 'longitude': longitude})

    @http.route("/sign/render_assets_pdf_iframe", type="jsonrpc", auth="public")
    def render_assets_pdf_iframe(self, **kw):
        context = {'debug': kw.get('debug')} if 'debug' in kw else {}
        return request.env['ir.ui.view'].sudo()._render_template('sign.compiled_assets_pdf_iframe', context)

    @http.route(['/sign/has_sms_credits'], type='jsonrpc', auth='public')
    def has_sms_credits(self):
        return request.env['iap.account'].sudo().get_credits('sms') >= 1

    def has_warning_for_service(self, roles, service_name):
        templates_using_service_roles = request.env['sign.template'].sudo().search([
            ('sign_item_ids.responsible_id', 'in', roles.ids)
        ])
        if templates_using_service_roles:
            requests_in_progress = request.env['sign.request'].sudo().search([
                ('template_id', 'in', templates_using_service_roles.ids),
                ('state', 'in', ['shared', 'sent'])
            ])

            if requests_in_progress and request.env['iap.account'].sudo().get_credits(service_name) < 20:
                return True
        return False

    def get_iap_credit_warnings(self):
        warnings = []
        roles_with_sms = request.env['sign.item.role'].sudo().search([('auth_method', '=', 'sms')])
        if roles_with_sms:
            if self.has_warning_for_service(roles_with_sms, 'sms'):
                warnings.append({
                    'iap_url': request.env['iap.account'].sudo().get_credits_url('sms'),
                    'auth_method': 'SMS'
                })
        return warnings

    @http.route(['/sign/sign_request_state/<int:request_id>/<token>'], type='jsonrpc', auth='public')
    def get_sign_request_state(self, request_id, token):
        """
        Returns the state of a sign request.
        :param request_id: id of the request
        :param token: access token of the request
        :return: state of the request
        """
        sign_request = request.env['sign.request'].sudo().browse(request_id).exists()
        if not sign_request or not consteq(sign_request.access_token, token):
            return http.request.not_found()
        return sign_request.state

    @http.route(['/sign/sign_request_items'], type='jsonrpc', auth='public')
    def get_sign_request_items(self, request_id, token, sign_item_id):
        """
        Finds up to 3 most important sign request items for the current user to sign,
        after the user has just completed one.
        :param request_id: id of the completed sign request
        :param token: access token of the request
        :return: list of dicts describing sign request items for the Thank You dialog
        """
        sign_request = request.env['sign.request'].browse(request_id).sudo()
        sign_item = request.env['sign.request.item'].browse(sign_item_id).sudo()
        if not sign_request.exists() or not consteq(sign_request.access_token, token) or not sign_item.exists():
            return []
        uid = sign_request.create_uid.id
        items = request.env['sign.request.item'].sudo().search_read(
            domain=[
                ('signer_email', '=', sign_item.signer_email),
                ('state', '=', 'sent'),
                ('sign_request_id.state', '=', 'sent'),
                ('id', '!=', sign_item.id)
            ],
            fields=['access_token', 'sign_request_id', 'create_uid', 'create_date'],
            order='create_date DESC',
            limit=20,
        )
        items.sort(key=lambda item: (0 if item['create_uid'] and uid == item['create_uid'][0] else 1))
        items = items[:3]
        return [{
            'id': item['id'],
            'token': item['access_token'],
            'requestId': item['sign_request_id'][0],
            'name': item['sign_request_id'][1],
            'userId': item['create_uid'][0] if item['create_uid'] else False,
            'user': item['create_uid'][1] if item['create_uid'] else False,
            'date': item['create_date'].date(),
        } for item in items]

    @http.route(['/sign/sign_cancel/<int:item_id>/<token>'], type='http', auth='public')
    def cancel_sign_request_item_from_mail(self, item_id, token):
        # TODO remove this route in 18.3, only here to support already sent emails
        sign_request_item = request.env['sign.request.item'].sudo().browse(item_id)
        return request.redirect('sign/document/mail/%s/%s?refuseDocument=1' % (sign_request_item.sign_request_id.id, token))
