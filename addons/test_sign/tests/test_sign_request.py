# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import tagged
from odoo.addons.sign.tests.sign_request_common import SignRequestCommon


@tagged('post_install', '-at_install')
class TestSignRequest(SignRequestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env['product.product'].create({'name': 'test_product'})

    def create_sign_request_wizard(self, model_name, record_id, subject):
        """Helper to create a sign request wizard with context from a reference document."""
        context = {
            'sign_directly_without_mail': False,
            'default_reference_doc': f'{model_name},{record_id}',
        }
        return self.env['sign.send.request'].with_context(context).create({
            'template_id': self.template_1_role.id,
            'subject': subject,
        })

    def test_send_request_with_default_partner_id(self):
        """Test default signer is set to partner_id for Sale Order."""

        sale_order = self.env['sale.order'].sudo().create({
            'partner_id': self.env.user.partner_id.id,
        })
        sale_order.action_confirm()

        wizard = self.create_sign_request_wizard(
            'sale.order',
            sale_order.id,
            'Test Sign Request for Sale Order'
        )
        default_signer = wizard._get_default_signer()

        self.assertEqual(default_signer, sale_order.partner_id.id,
            "Default signer should be the partner_id of the Sale Order"
        )

    def test_send_request_with_default_partner_id_for_crm(self):
        """Test default signer is set to partner_id for CRM Lead."""

        crm_lead = self.env['crm.lead'].sudo().create({
            'name': 'Test Lead',
            'partner_id': self.env.user.partner_id.id,
        })

        wizard = self.create_sign_request_wizard(
            'crm.lead',
            crm_lead.id,
            'Test Sign Request for CRM Lead'
        )
        default_signer = wizard._get_default_signer()

        self.assertEqual(default_signer, crm_lead.partner_id.id,
            "Default signer should be the partner_id of the CRM Lead"
        )

    def test_send_request_with_default_user_id(self):
        """Test default signer is set to user_id.partner_id for MRP Production."""

        mrp_production = self.env['mrp.production'].sudo().create({
            'product_id': self.product.id,
            'user_id': self.env.user.id,
        })

        wizard = self.create_sign_request_wizard(
            'mrp.production',
            mrp_production.id,
            'Test Sign Request for MRP'
        )
        default_signer = wizard._get_default_signer()

        self.assertEqual(default_signer, mrp_production.user_id.partner_id.id,
            "Default signer should be the partner_id of the user assigned to MRP"
        )

    def test_send_request_with_default_employee_id(self):
        """Test default signer is set to employee's work contact for Expense."""

        employee = self.env['hr.employee'].sudo().search([], limit=1)
        if not employee:
            self.skipTest("No employee available for test")

        expense = self.env['hr.expense'].sudo().create({
            'name': 'Test Expense',
            'employee_id': employee.id,
        })

        wizard = self.create_sign_request_wizard(
            'hr.expense',
            expense.id,
            'Test Sign Request for Expense'
        )
        default_signer = wizard._get_default_signer()

        self.assertEqual(default_signer, expense.employee_id.work_contact_id.id,
            "Default signer should be the employee's work contact ID"
        )

    def test_sign_request_auto_value(self):
        sale_order = self.env['sale.order'].sudo().create({
            'partner_id': self.env.user.partner_id.id,
            'order_line': [Command.create({
                    'product_id': self.product.id,
                    'price_unit': 500,
                }),
            ],
        })
        sale_order.action_confirm()
        type_id = self.env["sign.item.type"].create({
            'name': 'SO amount',
            'item_type': 'text',
            'model_id': self.env['ir.model']._get_id('sale.order'),
            'auto_field': 'amount_total',
        })
        template_constant = self.env['sign.template'].create({
            'name': 'template_constant',
        })
        document_id = self.env['sign.document'].create({
            'attachment_id': self.attachment.id,
            'template_id': template_constant.id,
        })
        self.env['sign.item'].create([{
            'type_id': type_id.id,
            'required': True,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1,
            'posX': 0.273,
            'posY': 0.158,
            'document_id': document_id.id,
            'width': 0.150,
            'height': 0.015,
            'constant': True,
        }])
        sign_request = self.env['sign.request'].with_context(no_sign_mail=False).create({
            'template_id': template_constant.id,
            'reference': "TEST",
            'reference_doc': f"sale.order,{sale_order.id}",
            'request_item_ids': [Command.create({
                'partner_id': self.partner_1.id,
                'role_id': self.env.ref('sign.sign_item_role_default').id,
            })],
        })
        item_value = self.env['sign.request.item.value'].search([('sign_request_id', '=', sign_request.id)])
        fetched_value = sign_request.request_item_ids._get_auto_field_value(type_id)
        self.assertEqual(sale_order.amount_total, fetched_value)
        self.assertEqual(str(sale_order.amount_total), item_value.value)
