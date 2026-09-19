# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.fields import Domain
from datetime import datetime
import hashlib
import re


class PosOrder(models.Model):
    _inherit = "pos.order"

    blackbox_date = fields.Char(
        "Fiscal Data Module date",
        help="Date returned by the Fiscal Data Module.",
        readonly=True,
    )
    blackbox_time = fields.Char(
        "Fiscal Data Module time",
        help="Time returned by the Fiscal Data Module.",
        readonly=True,
    )
    blackbox_pos_receipt_time = fields.Datetime("Receipt time", compute="_compute_blackbox_pos_receipt_time")
    blackbox_ticket_counters = fields.Char(
        "Fiscal Data Module ticket counters",
        help="Ticket counter returned by the Fiscal Data Module (format: counter / total event type)",
        readonly=True,
    )
    blackbox_unique_fdm_production_number = fields.Char(
        "Fiscal Data Module ID",
        help="Unique ID of the blackbox that handled this order",
        readonly=True,
    )
    blackbox_vsc_identification_number = fields.Char(
        "VAT Signing Card ID",
        help="Unique ID of the VAT signing card that handled this order",
        readonly=True,
    )
    blackbox_signature = fields.Char(
        "Electronic signature",
        help="Electronic signature returned by the Fiscal Data Module",
        readonly=True,
    )
    blackbox_order_sequence = fields.Char(
        "Blackbox order sequence",
        readonly=True,
    )
    blackbox_tax_category_a = fields.Monetary(
        readonly=True,
        string="Total tax for category A",
        help="This is the total amount of the 21% tax",
    )
    blackbox_tax_category_b = fields.Monetary(
        readonly=True,
        string="Total tax for category B",
        help="This is the total amount of the 12% tax",
    )
    blackbox_tax_category_c = fields.Monetary(
        readonly=True,
        string="Total tax for category C",
        help="This is the total amount of the 6% tax",
    )
    blackbox_tax_category_d = fields.Monetary(
        readonly=True,
        string="Total tax for category D",
        help="This is the total amount of the 0% tax",
    )
    plu_hash = fields.Char(help="Eight last characters of PLU hash")
    pos_version = fields.Char(help="Version of Odoo that created the order")
    is_clock = fields.Boolean("Is clock in/out", compute='_compute_is_clock')

    @api.depends("blackbox_date", "blackbox_time")
    def _compute_blackbox_pos_receipt_time(self):
        for order in self:
            if order.blackbox_date and order.blackbox_time:
                order.blackbox_pos_receipt_time = datetime.strptime(
                    order.blackbox_date + " " + order.blackbox_time, "%d-%m-%Y %H:%M:%S"
                )
            else:
                order.blackbox_pos_receipt_time = False

    def _compute_is_clock(self):
        work_products_set = set(self.env['pos.config']._get_work_products().ids)
        for order in self:
            order.is_clock = bool(work_products_set & set(order.lines.product_id.ids))

    @api.ondelete(at_uninstall=False)
    def unlink_if_blackboxed(self):
        for order in self:
            if order.config_id.certified_blackbox_identifier:
                raise UserError(_("Deleting of registered orders is not allowed."))

    @api.model
    def create_log(self, orders):
        for order in orders:
            self.env["pos_blackbox_be.log"].sudo().create([{
                    "action": "create",
                    "model_name": self._name,
                    "record_name": order['pos_reference'],
                    "description": self._create_log_description(order),
                }])
            self.env['pos.session'].browse(order['session_id'])._update_pro_forma(order)

    def _create_log_description(self, order):
        currency_id = self.env['res.currency'].browse(order['currency_id'])
        lines = []
        total = 0
        rounding_applied = 0
        hash_string = ""
        title = ""
        for line in order["lines"]:
            line_description = "{qty} x {product_name}: {price}".format(
                qty=line["qty"],
                product_name=line["product_name"],
                price=currency_id.round(line["price_subtotal_incl"]),
            )

            if line["discount"]:
                line_description += " (disc: {discount}%)".format(
                    discount=line["discount"]
                )

            lines.append(line_description)
        total = (
            currency_id.round(order["amount_total"])
            if order['state'] == "draft"
            else currency_id.round(order["amount_paid"])
        )
        rounding_applied = (
            0
            if order['state'] == "draft"
            else currency_id.round(order["amount_total"] - order["amount_paid"] + order["change"])
        )
        hash_string = order["plu_hash"]
        sale_type = ""
        if currency_id.round(order["amount_total"]) > 0:
            sale_type = " SALES"
        elif currency_id.round(order["amount_total"]) < 0:
            sale_type = " REFUNDS"
        else:
            if len(order["lines"]) == 0 or order["lines"][0]["qty"] >= 0:
                sale_type = " SALES"
            else:
                sale_type = " REFUNDS"
        title = ("PRO FORMA" if order['state'] == "draft" else "NORMAL") + sale_type

        order_type = order['config_name'] + (
            " Pro Forma/" if order['state'] == "draft" else " Pos Order/"
        )

        description = '''
        {title}
        Date: {create_date}
        Internal Ref: {pos_reference}
        Sequence: {blackbox_sequence}
        Cashier: {cashier_name}
        Order lines: {lines}
        Total: {total}
        Rounding: {rounding_applied}
        Ticket Counter: {ticket_counters}
        Hash: {hash}
        POS Version: {pos_version}
        FDM ID: {fdm_id}
        POS ID: {config_name}
        FDM Identifier: {fdmIdentifier}
        FDM Signature: {fdmSignature}
        '''.format(
            title=title,
            create_date=order['create_date'],
            cashier_name=order['employee_name'],
            lines="\n* " + "\n* ".join(lines),
            total=total,
            pos_reference=order['pos_reference'],
            blackbox_sequence=order_type + str(order['blackbox_order_sequence']).zfill(5),
            hash=hash_string,
            pos_version=order['pos_version'],
            ticket_counters=order['blackbox_ticket_counters'],
            fdm_id=order['blackbox_unique_fdm_production_number'],
            config_name=order['config_name'],
            fdmIdentifier=order['certified_blackbox_identifier'],
            rounding_applied=rounding_applied,
            fdmSignature=order['blackbox_signature'],
        )

        return description

    def _refund(self):
        work_products_ids = self.env['pos.config']._get_work_products().ids
        for order in self:
            if order.config_id.certified_blackbox_identifier:
                for line in order.lines:
                    if line.product_id.id in work_products_ids:
                        raise UserError(_("Refunding of WORK IN/WORK OUT orders is not allowed."))
        return super()._refund()

    def action_pos_order_cancel(self):
        cancellable_orders = self.filtered(lambda order: order.state == 'draft')
        if cancellable_orders:
            for order in cancellable_orders:
                order.write({
                    'blackbox_tax_category_a': 0,
                    'blackbox_tax_category_b': 0,
                    'blackbox_tax_category_c': 0,
                    'blackbox_tax_category_d': 0,
                })
        return super().action_pos_order_cancel()

    @api.model
    def search_paid_order_ids(self, config_id, domain, limit, offset):
        domain = Domain('lines.product_id', 'not in', self.env['pos.config']._get_work_products()) & Domain(domain)
        return super().search_paid_order_ids(config_id, domain, limit, offset)

    def _get_tax_amount_by_percent(self, tax_percent):
        return sum(
            line.price_subtotal_incl - line.price_subtotal
            for line in self.lines
            if line.tax_ids.amount_type == 'percent' and line.tax_ids.amount == tax_percent
        )

    def _get_plu(self):
        return hashlib.sha1(b''.join([line.blackbox_plu.encode('utf8') for line in self.lines])).hexdigest()[-8:]  # Circulaire AG Fisc Nr. 33/2016 Art. 43.l. take the last eight characters of the hash

    def _create_order_for_blackbox(self, clock=False, clock_in=True):
        now = datetime.now()
        self.write({
            'blackbox_order_sequence': self.config_id.get_NS_sequence_next(),
            'blackbox_tax_category_a': self._get_tax_amount_by_percent(21),
            'blackbox_tax_category_b': self._get_tax_amount_by_percent(12),
            'blackbox_tax_category_c': self._get_tax_amount_by_percent(6),
            'blackbox_tax_category_d': self._get_tax_amount_by_percent(0),
            'plu_hash': self._get_plu(),
        })
        return {
            'date': now.strftime('%Y%m%d'),
            'ticket_time': now.strftime('%H%M%S'),
            'insz_or_bis_number': self.sudo().config_id.current_session_id.user_id.insz_or_bis_number,
            'ticket_number': str(self.blackbox_order_sequence).lstrip('0'),
            'type': 'NS',
            'receipt_total': f"{abs(self.amount_total * 100):.0f}",
            'vat1': f"{abs(self.blackbox_tax_category_a * 100):03.0f}" if self.blackbox_tax_category_a else '',
            'vat2': f"{abs(self.blackbox_tax_category_b * 100):03.0f}" if self.blackbox_tax_category_b else '',
            'vat3': f"{abs(self.blackbox_tax_category_c * 100):03.0f}" if self.blackbox_tax_category_c else '',
            'vat4': f"{abs(self.blackbox_tax_category_d * 100):03.0f}" if self.blackbox_tax_category_d else '',
            'plu': self.plu_hash,
            'clock': ('in' if clock_in else 'out') if clock else False,
        }

    def _update_from_blackbox(self, data):
        date_str = data.get("date")
        time_str = data.get("time")
        self.write({
            'blackbox_signature': data.get("signature"),
            'blackbox_date': f"{date_str[6:]}-{date_str[4:6]}-{date_str[:4]}",
            'blackbox_time': f"{time_str[:2]}:{time_str[2:4]}:{time_str[4:]}",
            'blackbox_ticket_counters': "NS " + data.get("ticket_counter") + "/" + data.get("total_ticket_counter"),
            'blackbox_unique_fdm_production_number': data.get("fdm_number"),
            'blackbox_vsc_identification_number': data.get("vsc"),
        })


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    blackbox_plu = fields.Char("PLU hash", compute='_compute_plu_line')

    def _compute_plu_line(self):
        for line in self:
            if line.order_id.config_id.certified_blackbox_identifier:
                qty = line.qty
                description = line.product_id.display_name
                price = round(abs(line.price_subtotal_incl) * 100, 2)
                tax_labels = line.tax_ids.tax_group_id.mapped(lambda tg: tg.pos_receipt_label)
                tax_label = tax_labels[0] if len(tax_labels) > 0 else 'D'

                qty = line._prepare_number_for_plu(qty, 4)
                description = line._prepare_description_for_plu(description)
                price = line._prepare_number_for_plu(price, 8)

                line.blackbox_plu = qty + description + price + tax_label
            else:
                line.blackbox_plu = ''

    @api.model
    def _generate_translation_table(self):
        special_car = {
            ('Ä', 'Å', 'Â', 'Á', 'À', 'â', 'ä', 'á', 'à', 'ã'): 'A',
            ('Æ', 'æ'): 'AE',
            'ß': 'SS',
            ('ç', 'Ç'): 'C',
            ('Î', 'Ï', 'Í', 'Ì', 'ï', 'î', 'ì', 'í'): 'I',
            '€': 'E',
            ('Ê', 'Ë', 'É', 'È', 'ê', 'ë', 'é', 'è'): 'E',
            ('Û', 'Ü', 'Ú', 'Ù', 'ü', 'û', 'ú', 'ù'): 'U',
            ('Ô', 'Ö', 'Ó', 'Ò', 'ö', 'ô', 'ó', 'ò'): 'O',
            ('Œ', 'œ'): 'OE',
            ('ñ', 'Ñ'): 'N',
            ('ý', 'Ý', 'ÿ'): 'Y'
        }
        complete_table = {}
        for (key, value) in special_car.items():
            for char_key in key:
                complete_table[char_key] = value

        return complete_table

    @api.model
    def _replace_hash_and_sign_chars(self, string):
        translation_table = self._generate_translation_table()
        replaced_char = [translation_table[char] if char in translation_table else char.upper() for char in string]
        return ''.join(replaced_char)

    @api.model
    def _filter_allowed_hash_and_sign_chars(self, string):
        return re.sub(r'[^A-Z0-9]', '', string)

    @api.model
    def _prepare_number_for_plu(self, number, length):
        number = f"{abs(number):.0f}"
        number = self._replace_hash_and_sign_chars(number)
        number = self._filter_allowed_hash_and_sign_chars(number)
        number = number[-length:]
        return number.zfill(length)

    @api.model
    def _prepare_description_for_plu(self, description):
        description = self._replace_hash_and_sign_chars(description)
        description = self._filter_allowed_hash_and_sign_chars(description)
        description = description[-20:]
        return description.ljust(20)
