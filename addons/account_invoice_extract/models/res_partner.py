from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_created_by_ocr = fields.Boolean(default=False)

    _ocr_name_uniq = models.UniqueIndex(
        '(name, is_created_by_ocr) WHERE is_created_by_ocr = TRUE AND active = TRUE',
        "The OCR can't create multiple partners with the same name.",
    )
