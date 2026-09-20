import base64
import io
from collections import defaultdict

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.tools import misc, format_date
from odoo.tools.pdf import PdfFileReader, PdfFileWriter, PdfReadError, reshape_text

from odoo.addons.sign.utils.pdf_handling import get_valid_pdf_data

from PIL import UnidentifiedImageError

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


def _fix_image_transparency(image):
    """ Modify image transparency to minimize issue of grey bar artefact.
    When an image has a transparent pixel zone next to white pixel zone on a
    white background, this may cause on some renderer grey line artefacts at
    the edge between white and transparent.

    This method sets black transparent pixel to white transparent pixel which solves
    the issue for the most probable case. With this the issue happen for a
    black zone on black background but this is less likely to happen.
    """
    pixels = image.load()
    for x in range(image.size[0]):
        for y in range(image.size[1]):
            if pixels[x, y] == (0, 0, 0, 0):
                pixels[x, y] = (255, 255, 255, 0)


class SignDocument(models.Model):
    _name = 'sign.document'
    _description = 'Signature Document'
    _order = 'sequence'

    sequence = fields.Integer()
    attachment_id = fields.Many2one('ir.attachment', string="Attachment", required=True, index=True, ondelete='restrict')
    datas = fields.Binary(related='attachment_id.datas', readonly=False)
    name = fields.Char('Name', related='attachment_id.name', readonly=False)
    template_id = fields.Many2one('sign.template', 'Template', index=True, ondelete='cascade', required=True)
    sign_item_ids = fields.One2many('sign.item', 'document_id', string="Signature Items", copy=True)
    num_pages = fields.Integer('Number of pages', compute="_compute_num_pages", readonly=True, store=True)

    @api.depends('attachment_id.datas')
    def _compute_num_pages(self):
        for record in self:
            try:
                record.num_pages = self._get_pdf_number_of_pages(base64.b64decode(record.attachment_id.datas)) or 0
            except (ValueError, ValidationError):
                record.num_pages = 0

    @api.model_create_multi
    def create(self, vals_list):
        attachments = self.env['ir.attachment'].browse([vals.get('attachment_id') for vals in vals_list if vals.get('attachment_id')])
        for attachment in attachments:
            self._check_pdf_data_validity(attachment.datas)
        for vals, attachment in zip(vals_list, attachments):
            if attachment.res_model or attachment.res_id:
                vals['attachment_id'] = attachment.copy().id
            else:
                attachment.res_model = self._name
        documents = super().create(vals_list)
        for document, attachment in zip(documents, documents.attachment_id):
            attachment.write({
                'res_model': self._name,
                'res_id': document.id
            })
            if document.template_id.name == self.env._('New Template'):
                document.template_id.name = document.name
        documents.attachment_id.check_access('read')
        return documents

    @api.model
    def create_from_attachment_data(self, attachment_data_list, template_id):
        """
        Create sign.document records from a list of dictionaries containing attachment data.

        :param attachment_data_list: List of dictionaries, each with 'name' and 'datas' keys.
                                     Example: [{'name': 'asdf', 'datas': 'asdfasdfasdf23423'}, ...]
        :return: List the newly created sign.document records.
        :raises UserError: If the input list is empty or a dictionary is missing required keys.
        """
        if not attachment_data_list:
            raise UserError(self.env._("The attachment data list cannot be empty."))
        created_records = []
        for data in attachment_data_list:
            if not all(key in data for key in ['name', 'datas']):
                raise UserError(self.env._("Each item must contain 'name' and 'datas' keys."))
            attachment = self.env['ir.attachment'].create({
                'name': data['name'],
                'datas': data['datas'],
            })
            sign_document = self.create({
                'attachment_id': attachment.id,
                'sequence': data['sequence'],
                'template_id': template_id,
            })
            created_records.append(sign_document)
        return created_records

    def write(self, vals):
        res = super().write(vals)
        if 'attachment_id' in vals:
            self.attachment_id.check_access('read')
        return res

    def get_radio_sets_dict(self):
        """
        :return: dict radio_sets_dict that maps each radio set that belongs to
        this template to a dictionary containing num_options and radio_item_ids.
        """
        radio_sets = self.sign_item_ids.filtered(lambda item: item.radio_set_id).radio_set_id
        radio_sets_dict = {
            radio_set.id: {
                'num_options': radio_set.num_options,
                'radio_item_ids': radio_set.radio_items.ids,
            } for radio_set in radio_sets
        }
        return radio_sets_dict

    def _get_sign_items_by_page(self):
        self.ensure_one()
        items = defaultdict(lambda: self.env['sign.item'])
        for item in self.sign_item_ids:
            items[item.page] += item
        return items

    def update_attachment_name(self, name):
        """
        Updates the attachment's name. If the provided name is empty or None,
        the current name is retained. This forced update prevents the creation
        of duplicate sign items during simultaneous RPC requests.
        :param name: The new name for the attachment.
        :return:
            - True: Indicates the attachment name was successfully updated.
            - False: Indicates the update was skipped because a sign request linked
                    to the template already exists
        """
        self.ensure_one()
        sign_requests = self.env['sign.request'].search([('template_id', '=', self.template_id.id)], limit=1)
        if not sign_requests:
            self.attachment_id.name = name or self.attachment_id.name
            return True
        return False

    def _get_preview_values(self):
        """ prepare preview values based on current user and auto field"""
        self.ensure_one()
        values_dict = {}
        sign_item_type_date = self.env.ref('sign.sign_item_type_date', raise_if_not_found=False)
        phone_item_type = self.env.ref('sign.sign_item_type_phone', raise_if_not_found=False)
        company_item_type = self.env.ref('sign.sign_item_type_company', raise_if_not_found=False)
        email_item_type = self.env.ref('sign.sign_item_type_email', raise_if_not_found=False)
        name_item_type = self.env.ref('sign.sign_item_type_name', raise_if_not_found=False)
        with misc.file_open('sign/static/demo/signature.png', 'rb') as image_file:
            signature_b64 = base64.b64encode(image_file.read())
        with misc.file_open('sign/static/img/initial_example.png', 'rb') as image_file:
            initial_b64 = base64.b64encode(image_file.read())
        for it in self.sign_item_ids:
            role_name = it.responsible_id.name
            value = None
            if it.type_id == name_item_type:
                value = self.env._("%s's name", role_name)
            elif it.type_id == phone_item_type:
                value = "+1 555-555-5555 (%s)" % role_name
            elif it.type_id == company_item_type:
                value = self.env._("%s Company", role_name)
            elif it.type_id == email_item_type:
                value = "%s@example.com" % role_name.lower()
            elif it.type_id.item_type == "signature":
                value = "data:image/png;base64,%s" % signature_b64.decode()
            elif it.type_id.item_type == "initial":
                value = 'data:image/png;base64,%s' % initial_b64.decode()
            elif it.type_id.item_type == "text":
                if it.type_id != sign_item_type_date:
                    value = self.env._("Sample generated by Odoo for %s.", role_name)
                else:
                    value = format_date(self.env, fields.Date.today())
            elif it.type_id.item_type == "textarea":
                value = self.env._("""Odoo is a suite of open source business apps
that cover all your company needs:
CRM, eCommerce, accounting, inventory, point of sale,\nproject management, etc.
            """)
            elif it.type_id.item_type == "stamp":
                value = self.env._("""My US Company\n1034 Wildwood Street\n44654 Millersburg Ohio United States\n+1 555-555-5556""")
            elif it.type_id.item_type == "checkbox":
                value = "on"
            elif it.type_id.item_type == "selection":
                value = it.option_ids[:1].id  # we select always the first option
            elif it.type_id.item_type == "radio":
                radio_items = it.radio_set_id.radio_items
                value = "on" if it == radio_items[:1] else ""  # we select always the first option
            elif it.type_id.item_type == "strikethrough":
                value = "striked"
            values_dict[it.id] = {
                "value": value,
                "frame": "",
                'frame_has_hash': False,
            }
        signed_values = values_dict
        return signed_values, values_dict

    def _get_font(self):
        custom_font = self.env["ir.config_parameter"].sudo().get_param("sign.use_custom_font")
        # The font must be a TTF font. The tool 'otf2ttf' may be useful for conversion.
        if custom_font:
            pdfmetrics.registerFont(TTFont(custom_font, custom_font + ".ttf"))
            return custom_font
        return "Helvetica"

    def _get_normal_font_size(self):
        return 0.015

    @api.model
    def _get_page_size(self, pdf_reader):
        max_width = max_height = 0
        for page in pdf_reader.pages:
            media_box = page.mediaBox
            width = media_box and media_box.getWidth()
            height = media_box and media_box.getHeight()
            max_width = max(width, max_width)
            max_height = max(height, max_height)

        return (max_width, max_height) if max_width and max_height else None

    def render_document_with_items(self, signed_values=None, values_dict=None, final_log_hash=None):
        self.ensure_one()
        items_by_page = self._get_sign_items_by_page()
        if not signed_values or not values_dict:
            signed_values, values_dict = self._get_preview_values()
        try:
            old_pdf = PdfFileReader(io.BytesIO(self.attachment_id.raw), strict=False)
            old_pdf.getNumPages()
        except (ValueError, PdfReadError):
            raise ValidationError(self.env._("ERROR: Invalid PDF file!"))

        if old_pdf.isEncrypted:
            return

        font = self._get_font()
        normalFontSize = self._get_normal_font_size()

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=self._get_page_size(old_pdf))
        for p in range(0, old_pdf.getNumPages()):
            page = old_pdf.getPage(p)
            # Absolute values are taken as it depends on the MediaBox template PDF metadata, they may be negative
            width = float(abs(page.mediaBox.getWidth()))
            height = float(abs(page.mediaBox.getHeight()))

            # Add the final_log_hash as the certificate reference id on each page
            if final_log_hash:
                can.setFont(font, height * 0.01)
                ref_text = f"Signature: {final_log_hash}"
                can.drawCentredString(width / 3, height - 15, ref_text)

            # Set page orientation (either 0, 90, 180 or 270)
            rotation = page.get('/Rotate', 0)
            if rotation and isinstance(rotation, int):
                can.rotate(rotation)
                # Translate system so that elements are placed correctly
                # despite of the orientation
                if rotation == 90:
                    width, height = height, width
                    can.translate(0, -height)
                elif rotation == 180:
                    can.translate(-width, -height)
                elif rotation == 270:
                    width, height = height, width
                    can.translate(-width, 0)

            items = items_by_page.get(p + 1, [])
            for item in items:
                value_dict = signed_values.get(item.id)
                if not value_dict:
                    continue
                # only get the 1st
                value = value_dict['value']
                frame = value_dict['frame']
                if frame:
                    try:
                        image_reader = ImageReader(io.BytesIO(base64.b64decode(frame[frame.find(',') + 1:])))
                    except UnidentifiedImageError:
                        raise ValidationError(self.env._("There was an issue downloading your document. Please contact an administrator."))
                    _fix_image_transparency(image_reader._image)
                    can.drawImage(
                        image_reader,
                        width * item.posX,
                        height * (1 - item.posY - item.height),
                        width * item.width,
                        height * item.height,
                        'auto',
                        True
                    )

                if item.type_id.item_type == "text":
                    value = reshape_text(value)
                    can.setFont(font, height * item.height * 0.8)
                    if item.alignment == "left":
                        can.drawString(width * item.posX, height * (1 - item.posY - item.height * 0.9), value)
                    elif item.alignment == "right":
                        can.drawRightString(width * (item.posX + item.width), height * (1 - item.posY - item.height * 0.9), value)
                    else:
                        can.drawCentredString(width * (item.posX + item.width / 2), height * (1 - item.posY - item.height * 0.9), value)

                elif item.type_id.item_type == "selection":
                    text = ""
                    for option in item.option_ids:
                        if option.id == int(value):
                            text = option.value
                    font_size = height * normalFontSize * 0.8
                    string_width = stringWidth(text, font, font_size)
                    p = Paragraph(text, ParagraphStyle(name='Selection Paragraph', fontName=font, fontSize=font_size, leading=12))
                    posX = width * (item.posX + item.width * 0.5) - string_width // 2
                    posY = height * (1 - item.posY - item.height * 0.5) - p.wrap(width, height)[1] // 2
                    p.drawOn(can, posX, posY)

                elif item.type_id.item_type in ["textarea", "stamp"]:
                    font_size = height * normalFontSize * 0.8
                    can.setFont(font, font_size)
                    lines = value.split('\n')
                    y = (1 - item.posY)
                    for line in lines:
                        empty_space = width * item.width - can.stringWidth(line, font, font_size)
                        x_shift = 0
                        if item.alignment == 'center':
                            x_shift = empty_space / 2
                        elif item.alignment == 'right':
                            x_shift = empty_space
                        y -= normalFontSize * 0.9
                        line = reshape_text(line)
                        can.drawString(width * item.posX + x_shift, height * y, line)
                        y -= normalFontSize * 0.1

                    # Draw a dark blue border around the stamp field for visual emphasis
                    if item.type_id.item_type == "stamp":
                        padding = 5
                        itemW, itemH = item.width * width, item.height * height
                        itemX, itemY = item.posX * width, (1 - item.posY) * height
                        can.setLineWidth(1.2)  # thickness of border
                        can.setStrokeColorRGB(0, 0, 139 / 255)  # darkblue border
                        can.rect(
                            itemX - padding,
                            itemY - itemH - padding,
                            itemW + (2 * padding),
                            itemH + (2 * padding),
                            stroke=1,
                            fill=0
                        )

                elif item.type_id.item_type == "checkbox":
                    itemW, itemH = item.width * width, item.height * height
                    itemX, itemY = item.posX * width, (1 - item.posY) * height
                    meanSize = (itemW + itemH) // 2
                    can.setLineWidth(max(meanSize // 30, 1))
                    can.rect(itemX, itemY - itemH, itemW, itemH)
                    if value == 'on':
                        can.setLineWidth(max(meanSize // 20, 1))
                        can.bezier(
                            itemX + 0.20 * itemW, itemY - 0.35 * itemH,
                            itemX + 0.30 * itemW, itemY - 0.8 * itemH,
                            itemX + 0.30 * itemW, itemY - 1.2 * itemH,
                            itemX + 0.85 * itemW, itemY - 0.15 * itemH,
                        )
                elif item.type_id.item_type == "radio":
                    x = width * item.posX
                    y = height * (1 - item.posY)
                    w = item.width * width
                    h = item.height * height
                    # Calculate the center of the sign item rectangle.
                    c_x = x + w * 0.5
                    c_y = y - h * 0.5
                    # Draw the outer empty circle.
                    can.circle(c_x, c_y, h * 0.5)
                    if value == "on":
                        # Draw the inner filled circle.
                        can.circle(x_cen=c_x, y_cen=c_y, r=h * 0.5 * 0.75, fill=1)
                elif item.type_id.item_type == "signature" or item.type_id.item_type == "initial":
                    try:
                        image_reader = ImageReader(io.BytesIO(base64.b64decode(value[value.find(',') + 1:])))
                    except UnidentifiedImageError:
                        raise ValidationError(self.env._("There was an issue downloading your document. Please contact an administrator."))
                    _fix_image_transparency(image_reader._image)
                    can.drawImage(image_reader, width * item.posX, height * (1 - item.posY - item.height), width * item.width, height * item.height, 'auto', True)
                elif item.type_id.item_type == "strikethrough" and value == "striked":
                    x = width * item.posX
                    y = height * (1 - item.posY)
                    w = item.width * width
                    h = item.height * height
                    can.line(x, y - 0.5 * h, x + w, y - 0.5 * h)

            can.showPage()

        can.save()

        item_pdf = PdfFileReader(packet)
        new_pdf = PdfFileWriter()

        for p in range(0, old_pdf.getNumPages()):
            page = old_pdf.getPage(p)
            page.mergePage(item_pdf.getPage(p))
            new_pdf.addPage(page)

        output = io.BytesIO()
        try:
            new_pdf.write(output)
        except PdfReadError:
            raise ValidationError(self.env._("There was an issue downloading your document. Please contact an administrator."))

        return output

    def _copy_sign_items_to(self, new_document):
        """ Copy all sign items of the self document to the new_document that fit within its page count."""
        self.ensure_one()
        if new_document.template_id.has_sign_requests:
            raise UserError(self.env._("Somebody is already filling a document which uses this template"))

        new_document_pages = new_document.num_pages
        item_id_map = {}
        for sign_item in self.sign_item_ids:
            # Only copy sign items that fit within the new document's page range.
            if sign_item.page <= new_document_pages:
                new_sign_item = sign_item.copy({'document_id': new_document.id})
                item_id_map[str(sign_item.id)] = str(new_sign_item.id)
        return item_id_map

    @api.model
    def _check_pdf_data_validity(self, datas):
        try:
            self._get_pdf_number_of_pages(base64.b64decode(datas))
        except ValueError as e:
            raise UserError(self.env._("One uploaded file cannot be read. Is it a valid PDF?")) from e

    @api.model
    def _get_pdf_number_of_pages(self, pdf_data):
        file_pdf = get_valid_pdf_data(pdf_data, strict=False)
        return len(file_pdf.pages)
