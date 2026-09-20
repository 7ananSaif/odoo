# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.fields import Domain
from odoo.exceptions import UserError
from itertools import groupby
from collections import Counter


class PosSession(models.Model):
    _inherit = "pos.session"

    cash_box_opening_number = fields.Integer(
        help="Count the number of cashbox opening during the session"
    )
    users_clocked_ids = fields.Many2many(
        "res.users",
        "users_session_clocking_info",
        string="Users Clocked In",
        help="This is a technical field used for tracking the status of the session for each users.",
    )
    employees_clocked_ids = fields.Many2many(
        "hr.employee",
        "employees_session_clocking_info",
        string="Employees Clocked In",
        help="This is a technical field used for tracking the status of the session for each employees.",
    )

    pro_forma_sales_number = fields.Integer()
    pro_forma_sales_amount = fields.Monetary()
    pro_forma_refund_number = fields.Integer()
    pro_forma_refund_amount = fields.Monetary()

    correction_number = fields.Integer(
        help="Count the number of corrections during the session"
    )
    correction_amount = fields.Monetary(
        help="Sum of the amount of the corrections during the session"
    )

    def _load_pos_data_read(self, records, config):
        read_records = super()._load_pos_data_read(records, config)
        if read_records and config.certified_blackbox_identifier:
            record = read_records[0]
            session = self if self.exists() else self.env["pos.session"].browse(record["id"]).exists()
            record["_users_clocked_ids"] = session.users_clocked_ids.ids if session else []
            record["_employees_clocked_ids"] = session.employees_clocked_ids.ids if session else []
            record["_user_latest_clock_in"] = session._get_latest_user_clockin_date(config) if session else None
            if config.module_pos_hr:
                employees_insz_or_bis_number = self.env['hr.employee'].sudo().search_read(config._employee_domain(config.current_user_id.id), ['id', 'insz_or_bis_number'])
                insz_or_bis_number_per_employee_id = {employee['id']: employee['insz_or_bis_number'] for employee in employees_insz_or_bis_number}
                record["_employee_insz_or_bis_number"] = insz_or_bis_number_per_employee_id
        return read_records

    @api.depends("order_ids")
    def _compute_amount_of_vat_tickets(self):
        for rec in self:
            rec.amount_of_vat_tickets = len(rec.order_ids)

    def _set_opening_control_data(self, cashbox_value: int, notes: str):
        self.env['pos.blackbox.log.ip']._log_ip(self.config_id, None)
        super()._set_opening_control_data(cashbox_value, notes)

    def increase_cash_box_opening_counter(self):
        self.cash_box_opening_number += 1

    def increase_correction_counter(self, amount):
        self.correction_number += 1
        self.correction_amount += self.currency_id.round(amount)

    def set_user_session_work_status(self, user_id, status, all_insz):
        context = (
            "employees_clocked_ids"
            if self.config_id.module_pos_hr
            else "users_clocked_ids"
        )
        if all_insz:
            self.write({context: [(5,)]})
        elif status:
            self.write({context: [(4, user_id)]})
        else:
            self.write({context: [(3, user_id)]})
        self.config_id._notify("CLOCKING", {
            'session_id': self.id,
            'data': {
                'pos.session': self._load_pos_data_read(self, self.config_id),
            }
        })

    def _get_user_report_data(self):
        data = []

        orders = self.order_ids[::-1]  # orders are sorted by date_order asc and we want date_order desc, then it needs to be filtered by user_id and employee_id
        orders = orders.sorted(lambda order: order.employee_id.id or order.user_id.id)  # if one order has an employee id, every order should have one. Otherwise, no orders has an employee id.

        for k, g in groupby(orders, lambda order: order.employee_id or order.user_id):
            insz = k.sudo().insz_or_bis_number
            for order in g:
                if order.is_clock:
                    if order.lines[0].product_id.id == self.env.ref('pos_blackbox_be.product_product_work_in').id:
                        data.append({
                            'login': k.name,
                            'insz_or_bis_number': insz,
                            'revenue': 0,
                            'revenue_per_category': Counter(),
                            'first_ticket_time': order.date_order,
                            'last_ticket_time': False,
                            'fdmIdentifier': self.config_id.certified_blackbox_identifier,
                            'cash_rounding_applied': 0,
                        })
                    else:
                        data[-1]['last_ticket_time'] = order.date_order
                elif len(data) > 0 and not data[-1]['last_ticket_time']:
                    data[-1]['revenue'] += order.amount_paid
                    data[-1]['cash_rounding_applied'] += self.currency_id.round(order.amount_total - order.amount_paid)
                    total_sold_per_category = {}
                    for line in order.lines:
                        category_name = line.product_id.pos_categ_ids[0].name if len(line.product_id.pos_categ_ids) > 0 else "None"
                        if category_name not in total_sold_per_category:
                            total_sold_per_category[category_name] = 0
                        total_sold_per_category[category_name] += self.currency_id.round(line.price_subtotal_incl)

                    data[-1]['revenue_per_category'].update(Counter(total_sold_per_category))

        for info in data:
            info['revenue_per_category'] = list(info['revenue_per_category'].items())

        return data

    def action_report_journal_file(self):
        self.ensure_one()
        pos = self.config_id
        if not pos.iface_fiscal_data_module:
            raise UserError(_("PoS %s is not a certified PoS", pos.name))
        return {
            "type": "ir.actions.act_url",
            "url": "/journal_file/" + str(pos.certified_blackbox_identifier),
            "target": "self",
        }

    def _update_pro_forma(self, order):
        self.ensure_one()
        if order['state'] == "draft":
            amount_total = order['amount_total']
            if amount_total < 0:
                self.pro_forma_refund_number += 1
                self.pro_forma_refund_amount += self.currency_id.round(amount_total)
            else:
                self.pro_forma_sales_number += 1
                self.pro_forma_sales_amount += self.currency_id.round(amount_total)

    def get_total_discount_positive_negative(self, positive):
        order_ids = self.order_ids.ids
        price_operator = ">=" if positive else "<"

        orderlines = self.env["pos.order.line"].search(
            [("order_id", "in", order_ids), ("price_subtotal_incl", price_operator, 0), ("discount", ">", 0)]
        )

        amount = sum(
            line._get_discount_amount()
            for line in orderlines
        )

        return self.currency_id.round(amount)

    def check_everyone_is_clocked_out(self):
        if (
            self.config_id.module_pos_hr and len(self.employees_clocked_ids.ids) > 0
        ) or (
            not self.config_id.module_pos_hr and len(self.users_clocked_ids.ids) > 0
        ):
            raise UserError(_("You cannot close the POS with employees still clocked in. Please clock them out first."))

    def get_insz_clocked(self):
        insz_map = {}
        if self.config_id.module_pos_hr:
            for employee in self.employees_clocked_ids:
                insz_map[employee.id] = employee.sudo().insz_or_bis_number
        else:
            for user in self.users_clocked_ids:
                insz_map[user.id] = user.sudo().insz_or_bis_number
        return insz_map

    def _get_latest_user_clockin_date(self, config):
        self.ensure_one()

        work_in_product = self.env.ref('pos_blackbox_be.product_product_work_in', raise_if_not_found=False)
        if not work_in_product:
            return None

        domain = Domain('lines.product_id', '=', work_in_product.id)
        if config.module_pos_hr:
            domain &= Domain('employee_id', '=', self.employee_id.id)
        else:
            domain &= Domain('user_id', '=', self.user_id.id)
        order = self.env['pos.order'].search(domain, order='id desc', limit=1)
        return order.date_order if order else None
