# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import io
import json
import uuid
from werkzeug.urls import url_join

from odoo import _, http
from odoo.tools import consteq
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.tools.pdf import PdfFileReader, PdfReadError

from odoo.addons.iap import jsonrpc
from odoo.addons.sign.controllers.main import Sign as SignController
from odoo.addons.sign_emsigner.utils import compress_pdf_base64, decompress_pdf_base64
from odoo.addons.sign_emsigner.const import IAP_DEFAULT_DOMAIN

IAP_SERVICE_NAME = 'emsigner_proxy'


class SignEmsigner(SignController):

    def get_document_qweb_context(self, sign_request_id, token, **post):
        """
        Override to add show_emsigner_thank_you_dialog and error_message to the context
        """
        res = super().get_document_qweb_context(sign_request_id, token, **post)
        if res.get('rendering_context'):
            # show_thank_you_dialog and error_message come from IAP sign_emsigner redirect
            res['rendering_context']['show_emsigner_thank_you_dialog'] = post.get('show_emsigner_thank_you_dialog')
            res['rendering_context']['error_message'] = post.get('error_message')
        return res

    def _get_signature_fields_position(self, document_id, request_item_sudo):
        """ Compute the positions of all signature fields on the PDF for a given document and request item.

        This method retrieves all signature items associated with the given request item (typically
        based on role), and calculates their absolute positions on the PDF page.

        :param document_id: sign.document record
        :param request_item_sudo: sign.request.item record
        :return: dict of signature field positions
        """
        try:
            pdf_file_data = io.BytesIO(document_id.attachment_id.raw)
            pdf_file_reader = PdfFileReader(pdf_file_data, strict=False)
            pdf_file_reader.getNumPages()
        except (ValueError, PdfReadError) as e:
            raise ValidationError(self.env._("ERROR: Invalid PDF file! %s") % str(e))

        page_size = document_id._get_page_size(pdf_file_reader)
        pdf_width = float(page_size[0])
        pdf_height = float(page_size[1])

        # Get all signature items for the role
        signature_item_ids = request_item_sudo._get_current_signature_sign_items()
        fields_position = []

        for item in signature_item_ids:
            fields_position.append({
                'page': item.page,
                'left': pdf_width * item.posX,
                'top': pdf_height * (1 - item.posY),
                'width': (pdf_width * item.posX) + (pdf_width * item.width),
                'height': pdf_height * (1 - item.posY - item.height),
            })
        return fields_position

    def _is_file_large(self, file_size):
        """ Check if the file size exceeds the 10 MB limit.
        :param file_size: size of the file in bytes
        :return: bool
        """
        return file_size >= (1024 * 1024 * 9)  # 9 MB limit for compression

    def _get_emsigner_params(self, request_item_sudo, **kwargs):
        """ create the payload to send data to the emsigner portal

        :params request_item_sudo: sign.request.item record
        :return: dict
        """
        sign_request = request_item_sudo.sign_request_id
        document_id = sign_request.template_id.document_ids

        if len(document_id) != 1:
            raise ValidationError(
                self.env._("Emsigner only supports signing a single document at a time.")
            )

        signed_values = {}
        # Read the values of the sign request item values related to the sign request
        values_dict = self.env['sign.request.item.value'].sudo()._read_group(
            [('sign_request_id', '=', sign_request.id)],
            groupby=['sign_item_id'],
            aggregates=['value:array_agg', 'frame_value:array_agg', 'frame_has_hash:array_agg']
        )

        # Add current signer's values to the signed_values dict
        for sign_item, values, frame_values, frame_has_hashes in values_dict:
            signed_values[sign_item.id] = {
                'value': values[0],
                'frame': frame_values[0],
                'frame_has_hash': frame_has_hashes[0],
            }

        signature_info = kwargs.get('signatureInfo', {})
        frame_info = kwargs.get('frame', {})

        for key_str, value in signature_info.items():
            key = int(key_str)  # convert string key to int
            frame_data = frame_info.get(key_str, {})
            signed_values[key] = {
                'value': value,
                'frame': frame_data.get('frameValue'),
                'frame_has_hash': bool(frame_data.get('frameHash'))
            }

        final_log_hash = sign_request._get_final_signature_log_hash()
        output = document_id.render_document_with_items(
            signed_values=signed_values,
            values_dict=True,
            final_log_hash=final_log_hash
        )
        to_sign_data = output.getvalue()
        output.close()

        # Generate a unique reference number
        reference_number = uuid.uuid4().hex

        # Get the signature position on the pdf page
        signature_position = self._get_signature_fields_position(document_id, request_item_sudo)
        page_numbers = ",".join(str(item['page']) for item in signature_position)
        page_coordinates_with_page = ";".join([
            f"{item['page']},{item['left'] + 8},{item['top'] - (item['top'] - item['height'])},{item['width']},{item['height'] - 20}"
            for item in signature_position
        ])

        # Check if the file is large and needs compression
        is_file_large = self._is_file_large(file_size=document_id.attachment_id.file_size)
        if is_file_large:
            to_sign_data = compress_pdf_base64(to_sign_data)

        # Prepare the dynamic content for the emsigner
        dyamic_content = [
            {
                "Key": "eSigned using Aadhaar by",
                "Value": request_item_sudo.partner_id.email
            },
            {
                "Key": "Date",
                "Value": "DateTime"
            }
        ]
        dyamic_content_bytes = json.dumps(dyamic_content).encode('utf-8')
        dyamic_content_data = base64.b64encode(dyamic_content_bytes)

        return {
            "Name": request_item_sudo.partner_id.name,
            "FileType": "PDF",
            "SignatureMode": "12",  # 12 for Aadhaar based eSign
            "SelectPage": "PAGE LEVEL",
            "File": base64.b64encode(to_sign_data).decode('utf-8'),
            "PageNumber": page_numbers,
            "PreviewRequired": False,
            "PagelevelCoordinates": page_coordinates_with_page,
            "ReferenceNumber": reference_number,
            "EnableUploadSignature": False,
            "EnableFontSignature": False,
            "EnableDrawSignature": False,
            "EnableESignaturePad": False,
            "IsCompressed": is_file_large,
            "IsCosign": False,  # Make the value True if there are multiple signers
            "StoreToDB": True,
            "IsGSTN": False,
            "IsGSTN3B": False,
            "AuthenticationMode": 1,
            "Reason": f"Digitally Signed by {request_item_sudo.partner_id.email}",
            "DynamicContent": dyamic_content_data.decode('utf-8'),
        }

    def _validate_auth_method(self, request_item_sudo, **kwargs):
        if request_item_sudo.role_id.auth_method == 'emsigner':
            account = request.env['iap.account'].sudo().get(IAP_SERVICE_NAME)
            if not account.sudo().account_token:
                return {
                    'success': False,
                    'message': _("emSigner IAP service could not be found.")
                }
            endpoint = request.env['ir.config_parameter'].sudo().get_param(
                'sign_emsigner.iap_endpoint', IAP_DEFAULT_DOMAIN
            )
            emsigner_credits = request.env['iap.account'].sudo().get_credits(IAP_SERVICE_NAME)
            # If no credits are available, still allow signing without emsigner auth method
            if emsigner_credits < 1:
                request_item_sudo.signed_without_extra_auth = True
                return {
                    'success': True
                }
            params = {
                'signature_data': self._get_emsigner_params(request_item_sudo, **kwargs),
                'account_token': account.sudo().account_token,  # FOR IAP CREDIT
                'emsigner_state': '%s.%s' % (request_item_sudo.sign_request_id.id, request_item_sudo.access_token),
                'db_uuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid'),
                'url': account.get_base_url(),
            }
            response = jsonrpc(url_join(endpoint, '/api/emsigner/1/sign_identity_request'), params=params)
            return response
        return super()._validate_auth_method(request_item_sudo, **kwargs)

    # -------------
    #  HTTP Routes
    # -------------

    @http.route('/emsigner_sign/emsigner_successful', type='jsonrpc', auth='public', csrf='false')
    def sign_emsigner_complete(
        self, emsigner_state, reference_number, transaction_number, return_status, error_message, decrypted_data
    ):
        """ After successful signing, from emsigner portal, this method is called to complete the signing process for odoo side.
            :param emsigner_state: The state from emsigner, which contains sign_request_id and access_token
            :param reference_number: Unique reference from eMSigner
            :param transaction_number: The transaction number from emsigner
            :param return_status: The status of the signing process
            :param error_message: Any error message returned from emsigner
            :param decrypted_data: The signed document data in base64 format
            :return: dict indicating success or failure of the signing process
        """
        if not emsigner_state or error_message:
            return {
                'success': False,
            }
        sign_request_id, token = emsigner_state.split(".")
        items_sudo = request.env['sign.request.item'].sudo().search([
            ('sign_request_id', '=', int(sign_request_id)),
            ('state', '=', 'sent')
        ])

        request_item = next(
            (item for item in items_sudo if consteq(item.access_token, token)),
            None
        )

        if not (request_item and request_item.role_id.auth_method == 'emsigner'):
            return {
                'success': False
            }

        sign_user_sudo = request.env['res.users'].sudo().search(
            [('partner_id', '=', request_item.partner_id.id)],
            limit=1
        )
        if sign_user_sudo:
            # sign as a known user
            context = {}
            if request.env.user != sign_user_sudo and not request.env.user._is_public():
                context.update(logged_user_id=request.env.user.id)
            request_item = request_item.with_context(context).with_user(sign_user_sudo).sudo()

        sign_request = request_item.sign_request_id

        document_id = sign_request.template_id.document_ids
        if len(document_id) != 1:
            raise ValidationError(
                self.env._("Emsigner only supports signing a single document at a time.")
            )

        # Check if file is large and needs decompression
        file_size = document_id.attachment_id.file_size
        if self._is_file_large(file_size=file_size):
            decrypted_data = decompress_pdf_base64(decrypted_data)

        sign_request.completed_document_ids = request.env['sign.completed.document'].sudo().create({
            'sign_request_id': sign_request.id,
            'file': decrypted_data.encode() or sign_request.template_id.document_ids.datas,
            'document_id': sign_request.template_id.document_ids.id,
        })

        request_item._write_emsigner_data(reference_number, transaction_number, return_status)
        request_item._post_fill_request_item()

        return {
            'success': True
        }

    # CREDITS

    @http.route(['/emsigner/has_emsigner_credits'], type="jsonrpc", auth="public")
    def has_emsigner_credits(self):
        return request.env['iap.account'].sudo().get_credits(IAP_SERVICE_NAME) >= 1
