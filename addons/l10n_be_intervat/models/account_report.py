import base64
import io
import zipfile

from odoo import models
from odoo.exceptions import UserError


class IntervatTaxReportCustomHandler(models.AbstractModel):
    _inherit = 'l10n_be.tax.report.handler'

    def generate_zip_file_from_intervat(self, options):
        """ Fetch pdf and xml file from intervat for one vat declaration.

        :return: Zip file with both pdf and xml file of the declaration.
        """
        tax_return = self.env['account.return'].browse(options['return_id'])
        vat_declaration = self.env['l10n_be.vat.declaration'].search([
            ('return_id', '=', tax_return.id),
            ('rectification_declaration_id', '=', False),
        ], limit=1)
        if not vat_declaration:
            raise UserError(self.env._("No VAT declaration found for this period."))

        file_name = f"intervat_{options['date']['date_from']}_{options['date']['date_to']}"
        if not vat_declaration.declaration_file:
            pdf_file = vat_declaration.return_id.company_id._l10n_be_fetch_document_from_myminfin(vat_declaration.pdf_ref)
            xml_file = vat_declaration.return_id.company_id._l10n_be_fetch_document_from_myminfin(vat_declaration.xml_ref)

            with io.BytesIO() as buffer:
                with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zipfile_obj:
                    zipfile_obj.writestr(f"{file_name}.pdf", pdf_file)
                    zipfile_obj.writestr(f"{file_name}.xml", xml_file)

                file = {
                    'file_name': f"{file_name}.zip",
                    'file_content': buffer.getvalue(),
                    'file_type': 'zip',
                }
                tax_return._add_attachment(file)
                vat_declaration.declaration_file = base64.b64encode(file['file_content'])

                return file

        return {
            'file_name': f"{file_name}.zip",
            'file_content': base64.b64decode(vat_declaration.declaration_file),
            'file_type': 'zip',
        }
