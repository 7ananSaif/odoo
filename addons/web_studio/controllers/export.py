# Part of Odoo. See LICENSE file for full copyright and licensing details.
import io
import logging
import zipfile

from odoo.http import (
    Controller,
    content_disposition,
    request,
    route,
    serialize_exception,
)
from werkzeug.exceptions import Forbidden, InternalServerError, NotFound

from .export_utils import StudioExportSerializer

_logger = logging.getLogger(__name__)


class StudioExporter(Controller):
    @route('/web_studio/export', type='http', auth='user')
    def export(self, token, active_id):
        """ Exports a zip file containing the 'studio_customization' module
            gathering all customizations done with Studio (customizations of
            existing apps and freshly created apps) along with the
            StudioExportModel's related data.

            Returns:
                Response: A zip file containing the exported data

            Raises:
                Forbidden: If the user is not an admin.
                NotFound: If the export wizard is not found.
                InternalServerError: If the export wizard is not found.
        """
        if not self.env.is_admin():
            raise Forbidden()

        module = self.env['ir.module.module'].get_studio_module()
        wizard_id = int(active_id)
        wizard = self.env['studio.export.wizard'].browse(wizard_id).exists()
        if not wizard:
            raise NotFound()

        try:
            export_info = wizard.get_export_info()
            content = self.generate_archive(module, export_info)
            return request.make_response(content, headers=[
                ('Content-Disposition', content_disposition('customizations.zip')),
                ('Content-Type', 'application/zip'),
                ('Content-Length', len(content)),
            ])
        except Exception as e:
            _logger.warning("Error while generating studio export %s", module.name, exc_info=True)
            se = serialize_exception(e)
            error = {
                'code': 0,
                'message': "Odoo Server Error",
                'data': se
            }
            res = request.make_json_response(error, status=500)
            raise InternalServerError(response=res) from e

    def generate_archive(self, module, export_info):
        """ Returns a zip file containing the given module with the given data.
            Returns:
                bytes: A byte string containing the zip file.
        """
        with io.BytesIO() as f:
            with zipfile.ZipFile(f, 'w', zipfile.ZIP_STORED) as archive:
                for filename, content in self.generate_module_files(module, export_info):
                    archive.writestr(module.name + '/' + filename, content)
            return f.getvalue()

    def generate_module_files(self, module, export_info):
        """ Return an iterator of pairs (filename, content) to put in the exported
            module. Returned filenames are local to the module directory.
            Groups exported data by model in separated files.
            The content of the files is yielded as an encoded bytestring (utf-8)
            Yields:
                tuple: A tuple containing the filename and content.
        """
        yield from StudioExportSerializer(self.env, module, export_info).serialize()
