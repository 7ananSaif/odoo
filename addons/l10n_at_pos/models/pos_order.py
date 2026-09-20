import qrcode
import uuid
import io
import base64
from odoo import fields, models, _
from odoo.tools.float_utils import float_repr, float_is_zero
from odoo.addons.l10n_at_pos.models.fiskaly_client import FiskalyClient


class PosOrder(models.Model):
    _inherit = 'pos.order'

    l10n_at_pos_order_receipt_id = fields.Char(string="Receipt UUID", readonly=True, copy=False, help="Fiskaly receipt identifier for this order")
    l10n_at_pos_order_receipt_number = fields.Integer(string="Fiskaly Receipt Number", readonly=True, copy=False, help="Fiskaly receipt number for this order")
    l10n_at_pos_order_receipt_qr_data = fields.Char(string="Encrypted QRdata", readonly=True, copy=False, help="Fiskaly receipt signature QRdata for this order")
    is_fiskaly_order_receipt_signed = fields.Boolean(string="Receipt Signed?", readonly=True, copy=False, help="Fiskaly receipt signature status for this order")

    def _generate_qr_code_image(self, qr_data):
        qr = qrcode.make(qr_data)
        temp = io.BytesIO()
        qr.save(temp, format="PNG")
        return base64.b64encode(temp.getvalue()).decode("utf-8")

    def _l10n_at_amounts_per_vat(self):
        mapped_tax_groups = {
            "20%": "STANDARD",
            "10%": "REDUCED_1",
            "13%": "REDUCED_2",
            "0%": "ZERO",
        }

        result = []
        for line in self.lines:
            tax = line.tax_ids[0] if line.tax_ids else None
            tax_group_name = tax.tax_group_id.name if tax else "0%"
            vat_rate = mapped_tax_groups.get(tax_group_name, "SPECIAL")
            percentage = tax.amount if tax else 0
            vat_entry = {
                "vat_rate": vat_rate,
                "percentage": percentage,
                "incl_vat": line.price_subtotal_incl,
                "excl_vat": line.price_subtotal,
                "vat": line.price_subtotal_incl - line.price_subtotal
            }

            if vat_rate == "SPECIAL":
                existing_entry = next(
                    (entry for entry in result if entry["vat_rate"] == "SPECIAL" and float_is_zero(entry["percentage"] - vat_entry["percentage"], precision_digits=2)),
                    None,
                )
                if existing_entry:
                    existing_entry["incl_vat"] += vat_entry["incl_vat"]
                    existing_entry["excl_vat"] += vat_entry["excl_vat"]
                    existing_entry["vat"] += vat_entry["vat"]
                else:
                    result.append(vat_entry)
            else:
                if existing_entry := next((entry for entry in result if entry["vat_rate"] == vat_rate), None):
                    existing_entry["incl_vat"] += vat_entry["incl_vat"]
                    existing_entry["excl_vat"] += vat_entry["excl_vat"]
                    existing_entry["vat"] += vat_entry["vat"]
                else:
                    result.append(vat_entry)

        # Converting amounts in "^-?\\d+\\.\\d{2}$" format
        for entry_dict in result:
            for key, value in entry_dict.items():
                if isinstance(value, (int, float)):
                    entry_dict[key] = float_repr(value, 2)

        return result

    def action_prepare_receipts_queue(self):
        # Filter orders to include only those with 'l10n_at_pos_order_receipt_id', this ensures we process only orders created when Fiskaly was enabled,
        # particularly for configurations where Fiskaly is active, this approach is crucial in a multi-company setup.
        to_sign_orders = self.filtered(
            lambda order: not order.is_fiskaly_order_receipt_signed
                and order.l10n_at_pos_order_receipt_id and order.state != 'cancel'
            )
        if not to_sign_orders:
            return self.config_id.company_id._notify("info", _("No unsigned orders are found for the sessions synced with fiskaly of this company among the selected orders."))
        to_sign_orders.config_id.company_id._verify_required_fields()
        for order in to_sign_orders:
            order.sign_order_receipt()

    def sign_order_receipt(self, receipt_type="NORMAL"):
        self.ensure_one()
        company = self.company_id
        buyer = self.partner_id

        if not self.l10n_at_pos_order_receipt_id:
            self.l10n_at_pos_order_receipt_id = str(uuid.uuid4())
            self.env.cr.commit()

        vat_details = self._l10n_at_amounts_per_vat()
        receipt_data = {
            "receipt_type": receipt_type,
            "schema": {
                "ekabs_v0": {
                    "head": {
                        "id": str(self.id),
                        "number": str(self.pos_reference),
                        "date": self.date_order.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "seller": {
                            "name": company.name,
                            "tax_number": company.vat,
                            "tax_exemption": company.l10n_at_pos_is_tax_exempted,
                            "address": {
                                "street": (company.street or "") + (company.street2 or ""),
                                "postal_code": company.zip or "",
                                "city": company.city or "",
                                "country_code": "AUT",
                            }
                        },
                        "buyer": {
                            "name": buyer.name or "",
                            "address": {
                                "street": (buyer.street or "") + (buyer.street2 or ""),
                                "postal_code": buyer.zip or "",
                                "city": buyer.city or "",
                                "country_code": "AUT",
                            }
                        }
                    },
                    "data": {
                        "currency": self.currency_id.name,
                        "full_amount_incl_vat": float_repr(self.amount_total, 2),
                        "payment_types": [
                            {
                                "name": payment.payment_method_id.name,
                                "amount": float_repr(payment.amount, 2),
                            }
                            for payment in self.payment_ids
                        ],
                        "vat_amounts": vat_details,
                        "lines": [
                            {
                                "text": line.full_product_name,
                                "additional_text": (
                                    (f"Refunded Line of receipt id : {line.refunded_orderline_id.order_id.l10n_at_pos_order_receipt_id}" if line.refunded_orderline_id else "") +
                                    ", ".join(attr.display_name for attr in line.attribute_value_ids)
                                ),
                                "vat_amounts": [
                                    {
                                        "percentage": float_repr(line.tax_ids[0].amount if line.tax_ids else 0, 2),
                                        "incl_vat": float_repr(line.price_subtotal_incl, 2)
                                    }
                                ],
                                "item": {
                                    "number": line.product_id.id,
                                    "quantity": line.qty,
                                    "price_per_unit": float_repr(line.price_unit, 2),
                                },
                            }
                            for line in self.lines
                        ]
                    }
                }
            }
        }

        response = FiskalyClient(self.company_id, self.company_id.l10n_at_fiskaly_api_key, self.company_id.l10n_at_fiskaly_api_secret).sign_order(self.config_id.l10n_at_cash_regid, self.company_id.l10n_at_fiskaly_access_token, self.l10n_at_pos_order_receipt_id, receipt_data)
        self.l10n_at_pos_order_receipt_qr_data = self._generate_qr_code_image(response.get("qr_code_data"))
        self.l10n_at_pos_order_receipt_number = int(response.get("receipt_number"))
        self.is_fiskaly_order_receipt_signed = bool(response.get("signed"))
        return (self.is_fiskaly_order_receipt_signed, self.l10n_at_pos_order_receipt_number, self.l10n_at_pos_order_receipt_qr_data)
