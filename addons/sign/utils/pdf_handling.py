# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging

from io import BytesIO
from reportlab.pdfgen import canvas

from odoo.exceptions import ValidationError
from odoo.tools.pdf import DependencyError, DictionaryObject, errors, NameObject, PdfFileReader, PdfFileWriter, PdfReadError
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)


def get_valid_pdf_data(pdf_bytes, strict=True):
    """
    Validate and return a readable PDF file object from the given byte data.

    :param pdf_bytes: Raw byte data of the PDF file to be validated.
    :param strict: Enforce strict parsing of the PDF file.
    :return: A valid and non-encrypted PdfFileReader instance.
    :raises ValidationError: If cannot return non-encrypted PdfFileReader instance.
    """
    try:
        pdf_reader = PdfFileReader(BytesIO(pdf_bytes), strict)
        if not pdf_reader.isEncrypted:
            return pdf_reader
    except (DependencyError, UnicodeDecodeError, PdfReadError):
        _logger.warning("Failed to read PDF data.")

    raise ValidationError(_lt(
        "It seems that we're not able to process one of the uploaded pdf. It is either"
        " encrypted, or encoded in a format we do not support."
    ))


def flatten_pdf(base64_pdf):
    """
    Flatten a PDF by rendering all form field values as static text and
    removing interactive form elements (/Annots and /AcroForm).

    :param base64_pdf: Base64-encoded string of the original PDF.
    :return: Base64-encoded string of the flattened, non-editable PDF.
    :raises ValidationError: If the PDF cannot be decoded or parsed.
    """
    try:
        pdf_bytes = base64.b64decode(base64_pdf)
        pdf_reader = get_valid_pdf_data(pdf_bytes)
        output_pdf = PdfFileWriter()
    except errors.PyPdfError as e:
        _logger.warning("Failed to parse PDF during flattening: %s", e)
        return base64_pdf

    if not pdf_reader.getFormTextFields():
        return base64_pdf  # No fields to flatten

    for page_num in range(pdf_reader.getNumPages()):
        try:
            page = pdf_reader.getPage(page_num)
            annotations = page.get("/Annots")
            if not annotations:
                output_pdf.addPage(page)
                continue

            # Dynamic page size
            page_width = float(page.mediaBox.getWidth())
            page_height = float(page.mediaBox.getHeight())
            packet = BytesIO()
            can = canvas.Canvas(packet, pagesize=(page_width, page_height))

            # Draw each field value
            for annot_ref in annotations:
                _draw_field_value(can, annot_ref)

            # Save overlay and merge with original page
            can.save()
            packet.seek(0)  # reset cursor to beginning before reading

            # Read the overlay PDF we just created from memory
            # And place it on top of the original page to show the field values
            overlay_pdf = PdfFileReader(packet)
            page.mergePage(overlay_pdf.getPage(0))

            # Remove interactive annotations so the result is read-only
            del page["/Annots"]
            output_pdf.addPage(page)

        except errors.PyPdfError:
            return base64_pdf

    # Remove AcroForm metadata (fully disable interactive forms)
    output_pdf._root_object.update({
        NameObject("/AcroForm"): DictionaryObject()
    })

    output_stream = BytesIO()
    output_pdf.write(output_stream)
    return base64.b64encode(output_stream.getvalue())


def _draw_field_value(can, annot_ref):
    """
    Auxiliary function to draw a field value (text, checkbox, radio button).
    """
    annot = annot_ref.getObject()
    rect = annot.get("/Rect")
    if not rect:
        return

    x, y = float(rect[0]), float(rect[1])
    field_value = ""
    can.setFont("Helvetica", 10)

    # Render a ✓ symbol for checked Check Box or Radio Button
    appearance_state = annot.get("/AS")
    if appearance_state and appearance_state != NameObject("/Off"):
        field_value = chr(0x2713)
    elif annot.get("/V") != "/Off":
        field_value = str(annot.get("/V") or "")

    if field_value:
        can.drawString(x + 2, y + 2, field_value)
