# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.fields import Domain


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    product_template_id = fields.Many2one('product.template', string="Product", compute='_compute_product', search='_search_product_template_id')
    product_id = fields.Many2one('product.product', string="Product Variant", compute='_compute_product', search='_search_product_id')

    @api.depends('res_id', 'res_model')
    def _compute_product(self):
        ProductTemplate = self.env['product.template']
        Product = self.env['product.product']
        for document in self:
            document.product_template_id = document.res_model == 'product.template' and ProductTemplate.browse(document.res_id)
            document.product_id = document.res_model == 'product.product' and Product.browse(document.res_id)

    @api.model
    def _search_product_template_id(self, operator, value):
        return self._search_related_product_field(operator, value, 'product_template_id')

    @api.model
    def _search_product_id(self, operator, value):
        return self._search_related_product_field(operator, value, 'product_id')

    @api.model
    def _search_related_product_field(self, operator, value, field_name) -> Domain:
        assert field_name in ('product_template_id', 'product_id')
        Model = self.env[self._fields[field_name].comodel_name]
        if operator == 'in':
            if True in value:
                # support for True value
                return Domain(field_name, 'not in', [False]) | Domain(field_name, 'in', value - {True})
            if False in value:
                return Domain('res_model', '!=', Model._name) | self._search_related_product_field(operator, value - {False}, field_name)
            query_model = Model._search(Domain.OR(
                Domain(Model._rec_name if isinstance(v, str) else 'id', operator, v)
                for v in value
                if v
            ))
        elif operator == 'any' and isinstance(value, Domain):
            query_model = Model._search(value)
        elif operator.endswith('like') and not operator.startswith('not'):
            query_model = Model._search([(Model._rec_name, operator, value)])
        else:
            return NotImplemented
        return (Domain.FALSE if query_model.is_empty() else Domain('res_id', 'in', query_model)) & Domain('res_model', '=', Model._name)

    def create_product_template(self):
        # JUC: WTF? A single product for many documents, and the created
        #      product has the image of the first document?!

        product = self.env['product.template'].create({
            'name': _('Product created from Documents')
        })

        for document in self:
            if document.res_model or document.res_id:
                att_copy = document.attachment_id.with_context(no_document=True).copy()
                document = document.copy({'attachment_id': att_copy.id})
            document.write({
                'res_model': product._name,
                'res_id': product.id,
            })
            is_image = (document.mimetype or '').partition('/')[0] == 'image'
            if is_image and not product.image_1920:
                product.write({'image_1920': document.datas})

        view_id = product.get_formview_id()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'name': "New product template",
            'context': self.env.context,
            'view_mode': 'form',
            'views': [(view_id, "form")],
            'res_id': product.id,
            'view_id': view_id,
        }

    def write(self, vals):
        """Sync product.document attachment when a document sharing a common
        attachment with a product/template is updated."""
        documents_for_products = self.filtered(
            lambda d: d.res_model in ('product.template', 'product.product')
            and d.attachment_id
        )
        if 'attachment_id' not in vals or not documents_for_products:
            return super().write(vals)
        document_by_old_attachment = documents_for_products.grouped('attachment_id')
        res = super().write(vals)
        product_docs = self.env['product.document'].search([
            ('ir_attachment_id', 'in', [a.id for a in document_by_old_attachment])
        ])
        for product_doc in product_docs:
            updated_related_document = document_by_old_attachment[product_doc.ir_attachment_id]
            product_doc.ir_attachment_id = updated_related_document.attachment_id
        return res
