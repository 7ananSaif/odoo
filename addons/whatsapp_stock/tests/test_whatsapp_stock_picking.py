from odoo import Command
from odoo.addons.stock.tests.common import TestStockCommon
from odoo.addons.whatsapp.tests.common import WhatsAppCommon, MockOutgoingWhatsApp


class WhatsappStockPicking(TestStockCommon, WhatsAppCommon, MockOutgoingWhatsApp):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner',
            'phone': '+91 12345 67890',
        })
        cls.wa_template = cls.env['whatsapp.template'].create({
            'body': 'The stock movement has been validated successfully.',
            'model_id': cls.env['ir.model']._get_id('stock.picking'),
            'name': 'Test Whatsapp Stock Picking',
            'phone_field': 'partner_id.phone',
            'status': 'approved',
            'wa_account_id': cls.whatsapp_account.id,
        })

    def test_whatsapp_stock_picking(self):
        picking = self.env['stock.picking'].create({
            'location_dest_id': self.customer_location.id,
            'location_id': self.stock_location.id,
            'partner_id': self.partner.id,
            'picking_type_id': self.picking_type_out.id,
            'move_line_ids': [
                Command.create({
                    'product_id': self.productA.id,
                    'product_uom_id': self.productA.uom_id.id,
                    'location_id': self.stock_location.id,
                    'location_dest_id': self.customer_location.id,
                    'quantity': 1,
                }),
            ],
        })
        self.env.company.stock_confirmation_type = 'whatsapp'
        self.env.company.stock_confirmation_wa_template_id = self.wa_template.id
        with self.mockWhatsappGateway():
            picking.button_validate()
        self.assertWAMessage(
            'outgoing',
            fields_values={
                'body': '<p>The stock movement has been validated successfully.</p>',
                'mobile_number': '+91 12345 67890',
            },
        )
