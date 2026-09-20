from odoo import models, fields


class ExtractMixinWithWords(models.AbstractModel):
    _name = 'extract.mixin.with.words'
    _inherit = ['extract.mixin']
    _description = 'Base class to extract data from documents with OCRed words saved'

    extract_attachment_id = fields.Many2one('ir.attachment', readonly=True, ondelete='set null', copy=False, index='btree_not_null')
    extracted_words = fields.Json()
    extracted_numbers = fields.Json()
    extracted_dates = fields.Json()

    def _upload_to_extract_success_callback(self):
        super()._upload_to_extract_success_callback()
        self.extract_attachment_id = self.message_main_attachment_id

    ### Methods for the OCR correction feature ###

    def _on_ocr_results(self, ocr_results):
        super()._on_ocr_results(ocr_results)
        self.extracted_words = ocr_results.get('words', {})
        self.extracted_numbers = ocr_results.get('numbers', {})
        self.extracted_dates = ocr_results.get('dates', {})

    def get_boxes(self):
        i = 0
        return {
            box_type: {
                page_number: [
                    {
                        'id': (i := i + 1),
                        'text': box['content'],
                        'page': page_number,
                        'minX': box['coords'][0] - box['coords'][2] / 2,
                        'midX': box['coords'][0],
                        'maxX': box['coords'][0] + box['coords'][2] / 2,
                        'minY': box['coords'][1] - box['coords'][3] / 2,
                        'midY': box['coords'][1],
                        'maxY': box['coords'][1] + box['coords'][3] / 2,
                        'width': box['coords'][2],
                        'height': box['coords'][3],
                        'angle': box['coords'][4],
                    } for box in boxes]
                for page_number, boxes in data.items()
            }
            for box_type, data in (
                ('word', self.extracted_words or {}),
                ('number', self.extracted_numbers or {}),
                ('date', self.extracted_dates or {}),
            )
        }

    def get_currency_from_text(self, text):
        self.ensure_one()
        if not text:
            return None

        currencies = self.env['res.currency'].search([])
        for curr in currencies:
            if text.lower() in (curr.currency_unit_label.lower(), curr.name.lower(), curr.symbol):
                return curr.id
        return None
