# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io
import zipfile
from os.path import join as opj
from werkzeug.utils import secure_filename


from odoo import http
from odoo.http import Stream, request
from odoo.tools import consteq


class WhatsappSign(http.Controller):

    def _split_filename(self, filename):
        """ Manually split a filename into (base_name, extension).

        :param str filename: The file name string
        :return: The base name and extension (extension includes the leading dot)
        :rtype: tuple
        """
        dot_index = filename.rfind('.')

        # No dot or dot is first character (e.g. ".bashrc")
        if dot_index <= 0:
            return filename, ''

        base_name = filename[:dot_index]
        ext = filename[dot_index:]  # includes the dot
        return base_name, ext

    def _generate_sign_request_zip_name(self, sign_request):
        """ Generates a sanitized base name for the ZIP file and its internal folder
        based on the sign request's subject or a default fallback.
        This method removes any file extension (e.g., ".pdf") from the subject,
        strips unsafe characters, and replaces spaces with underscores to create
        a safe filename.

        :param sign_request: The sign request record
        :return: A sanitized base name to use for the ZIP file and its internal folder
        :rtype: str
        """
        subject = sign_request.subject
        if subject:
            # Remove any file extension (e.g., ".pdf")
            name, _ = self._split_filename(subject)
        else:
            name = request.env._("Attachments of Request %s", str(sign_request.reference))

        return secure_filename(name)

    def _create_zip_response(self, sign_request):
        """ Creates a ZIP file containing multiple attachments for sign requests.

        :params Model.model sign_request: The sign request record
        :return: A streamed HTTP response containing the ZIP file
        """
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zipfile_obj:
            existing_document_names = set()
            for attachment in sign_request.attachment_ids:
                download_name = self._format_attachments_name(
                    sign_request, attachment, existing_document_names
                )
                zipfile_obj.writestr(download_name, attachment.raw)

        content = buffer.getvalue()
        filename = f'{self._generate_sign_request_zip_name(sign_request)}.zip'

        return Stream(
            type='data',
            data=content,
            mimetype='application/zip',
            download_name=filename,
            as_attachment=True,
            size=len(content),
        ).get_response()

    def _format_attachments_name(self, sign_request, attachment, existing_document_names):
        """ Generates a unique, sanitized attachment name prefixed with the sign request folder.
        Ensures the attachment name does not conflict with existing names by appending a counter
        if necessary, preserving the file extension.

        :param sign_request: The sign request record
        :param attachment: The attachment to be named
        :param set existing_document_names: Set of existing attachment names to check for duplicates
        :return: A unique attachment name with folder prefix
        :rtype: str
        """
        zip_name = self._generate_sign_request_zip_name(sign_request)
        base_name, ext = self._split_filename(attachment.name)
        download_name = attachment.name
        counter = 1

        while download_name in existing_document_names:
            download_name = f"{base_name} ({counter}){ext}"
            counter += 1
        existing_document_names.add(download_name)

        # Prepend the zip folder name after resolving duplicates
        download_name = opj(zip_name, download_name)

        return download_name

    @http.route([
        '/sign/download/attachments/<int:request_id>/<token>',
        '/sign/download/attachments/<int:request_id>/<token>/<int:sign_attachment_id>'
    ], type='http', auth='public')
    def download_attachment(self, request_id, token, attachment_id=None, **post):
        """ Handles downloading attachments related to a sign request.
        This method processes requests to download one or all attachments associated with
        a sign request. It authenticates the request using the provided token and returns
        either the specified attachment (if an attachment ID is provided and valid), or
        all attachments related to the sign request.

        :param int request_id: ID of the sign request
        :param str token: Access token used to authorize the request
        :param int attachment_id: ID of a specific attachment to download
        :param post: Additional POST parameters (currently unused)
        :return: A response containing the specified attachment or all attachments,
        or an appropriate redirect or error response if no valid attachments are found
        or access is unauthorized
        """
        sign_request = request.env['sign.request'].sudo().browse(request_id).exists()
        if not sign_request or not consteq(sign_request.access_token, token):
            return request.not_found()

        if attachment_id:
            attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
            if attachment in sign_request.attachment_ids:
                return attachment._to_http_stream().get_response(as_attachment=True)
            else:
                return request.not_found()

        attachment_ids = sign_request.attachment_ids
        if len(attachment_ids) == 1:
            return attachment_ids._to_http_stream().get_response(as_attachment=True)
        elif len(attachment_ids) > 1:  # If there are multiple attachments and no specific ID was provided, create a ZIP
            return self._create_zip_response(sign_request)

        return request.not_found()
