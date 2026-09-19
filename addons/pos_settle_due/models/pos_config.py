from odoo import models, fields, api

class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _get_default_settle_product(self):
        return self.env.ref("pos_settle_due.product_product_settle", raise_if_not_found=False) or self.env['product.product']

    def _get_default_deposit_product(self):
        return self.env.ref("pos_settle_due.product_product_deposit", raise_if_not_found=False) or self.env['product.product']

    def _get_default_settle_invoice_product(self):
        return self.env.ref("pos_settle_due.product_product_settle_invoice", raise_if_not_found=False) or self.env['product.product']

    settle_due_product_id = fields.Many2one('product.product', default=_get_default_settle_product, string='Settle Due Product', help="This product is used as to settle due of customer account.")
    deposit_product_id = fields.Many2one('product.product', default=_get_default_deposit_product, string='Deposit Product', help="This product is used to deposit money on customer account.")
    settle_invoice_product_id = fields.Many2one('product.product', default=_get_default_settle_invoice_product, string='Settle Invoice Product', help="This product is used as to settle invoices of customer.")

    @api.model
    def _default_settle_deposit_product_on_module_install(self):
        configs = self.env['pos.config'].search([])
        open_configs = (
            self.env['pos.session']
            .search(['|', ('state', 'in', ['opened', 'closing_control']), ('rescue', '=', True)])
            .mapped('config_id')
        )
        product_settle = self._get_default_settle_product()
        product_deposit = self._get_default_deposit_product()
        product_settle_inv = self._get_default_settle_invoice_product()
        for conf in (configs - open_configs):
            conf.settle_due_product_id = product_settle
            conf.deposit_product_id = product_deposit
            conf.settle_invoice_product_id = product_settle_inv

    def _get_special_products(self):
        res = super()._get_special_products() | self._get_default_settle_product() | self._get_default_deposit_product() | self._get_default_settle_invoice_product()

        return res
