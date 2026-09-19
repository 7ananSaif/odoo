# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib
import pathlib
import logging

from markupsafe import Markup

from odoo import http
from odoo.http import request
from odoo.modules import get_module_path
from odoo.addons.point_of_sale.controllers.main import PosController
from odoo.addons.pos_self_order.controllers.orders import PosSelfOrderController
from odoo.tools import consteq
from odoo.service.common import exp_version

from werkzeug.exceptions import Unauthorized

_logger = logging.getLogger(__name__)


BLACKBOX_MODULES = ['pos_blackbox_be']
class GovCertificationController(http.Controller):
    @http.route('/fdm_source', auth='user')
    def handler(self):
        root = pathlib.Path(__file__).parent.parent.parent

        modfiles = [
            p
            for modpath in map(pathlib.Path, map(get_module_path, BLACKBOX_MODULES))
            for p in modpath.glob('**/*')
            if p.is_file()
            if p.suffix in ('.py', '.xml', '.js', '.csv')
            if '/tests/' not in str(p)
        ]
        modfiles.sort()

        files_data = []
        main_hash = hashlib.sha1()
        for p in modfiles:
            content = p.read_bytes()
            content_hash = hashlib.sha1(content).hexdigest()
            files_data.append({
                'name': str(p.relative_to(root)),
                'size_in_bytes': p.stat().st_size,
                'contents': Markup(content.decode()),
                'hash': content_hash
            })
            main_hash.update(content_hash.encode())

        data = {
            'files': files_data,
            'main_hash': main_hash.hexdigest(),
        }

        return request.render('pos_blackbox_be.fdm_source', data, mimetype='text/plain')

    @http.route("/journal_file/<string:serial>", auth="user")
    def journal_file(self, serial, **kw):
        # Give the journal file report for a specific blackbox serial: e.g. BODO001bd6034a
        logs = request.env["pos_blackbox_be.log"].search([
            ("action", "=", "create"),
            ("description", "ilike", serial),
        ], order='id')

        data = {
            'pos_id': serial,
            'logs': logs,
        }

        return request.render("pos_blackbox_be.journal_file", data, mimetype="text/plain")


class BlackboxPosSelfController(PosSelfOrderController):
    @http.route('/pos_blackbox_be/send_order', auth='public', type='jsonrpc', website=True)
    def pos_self_blackbox_send_order(self, access_token, order_access_token, order_id):
        pos_config = self._verify_pos_config(access_token)
        order = pos_config.current_session_id.order_ids.browse(order_id)
        if not order or not consteq(order_access_token, order.access_token):
            return False

        return bool(order.blackbox_signature) or pos_config._send_order_to_blackbox(order)

    @http.route('/pos_self_blackbox/confirmation', methods=['POST'], auth='public', type='jsonrpc')
    def pos_self_blackbox_confirmation(self):
        def get_log_fields(order, data):
            return [{
                'state': order.state,
                'create_date': order.date_order,
                'employee_name': order.user_id.name if order.config_id.module_pos_hr else order.cashier,
                'amount_total': order.amount_total,
                'amount_paid': order.amount_paid,
                'currency_id': order.currency_id.id,
                'pos_reference': order.pos_reference,
                'config_name': order.config_id.name,
                'session_id': order.session_id.id,
                'lines': [
                    {
                        "product_name": line.product_id.display_name,
                        "qty": line.qty,
                        "price_subtotal_incl": line.price_subtotal_incl,
                        "discount": line.discount,
                    }
                    for line in order.lines
                ],
                'blackbox_order_sequence': order.blackbox_order_sequence,
                'plu_hash': order.plu_hash,
                'pos_version': exp_version()['server_serie'],
                'blackbox_ticket_counters': order.blackbox_ticket_counters,
                'blackbox_unique_fdm_production_number': order.blackbox_unique_fdm_production_number,
                'certified_blackbox_identifier': order.config_id.certified_blackbox_identifier,
                'blackbox_signature': order.blackbox_signature,
                'change': 0,
            }]
        data = request.get_json_data()
        device_identifier = data.get("device_identifier")
        iot_mac = data.get("iot_mac")
        if isinstance(device_identifier, str):
            box = request.env['iot.box'].sudo().search([('identifier', '=', iot_mac)], limit=1)
            if not box:
                _logger.warning("No IoT found with mac/identifier '%s'. Request ignored", iot_mac)
                return
            blackbox = request.env["iot.device"].sudo().search([
                    ('identifier', '=', device_identifier),
                    ('iot_id', '=', box.id)
                ],
                limit=1
            )

            if not blackbox:
                _logger.warning("No blackbox found with identifier '%s' (iot_mac: %s). Request ignored", device_identifier, iot_mac)
                return

            order = request.env["pos.order"].sudo().browse(data.get("order_id"))
            order._update_from_blackbox(data['blackbox_response'])
            work_products = request.env["pos.config"]._get_work_products()
            if set(order.lines.product_id) & set(work_products):
                data["orderAccessToken"] = order.access_token
                data["orderId"] = order.id
                if order.lines[0].product_id.id == request.env.ref('pos_blackbox_be.product_product_work_in').id:
                    order.session_id.write({'users_clocked_ids': [(4, order.user_id.id)]})
                else:
                    order.session_id.write({'users_clocked_ids': [(3, order.user_id.id)]})
                order.config_id._notify("BLACKBOX_CLOCK", data)
            order.config_id._notify("BLACKBOX_CONFIRMATION", data)
            order.create_log(get_log_fields(order, data))

    @http.route('/pos_self_blackbox/clock', auth='public', type='jsonrpc', website=True)
    def pos_self_blackbox_clock(self, access_token, config_id, clock_in=True):
        pos_config = self._get_pos_config_force(access_token, config_id)
        clocked_users = pos_config.current_session_id.users_clocked_ids
        if (clock_in and len(clocked_users) > 0) or (not clock_in and len(clocked_users) == 0):
            return
        pos_config._clock_kiosk_user(clock_in)
        return

    @http.route('/pos_self_blackbox/get_clock_order', auth='public', type='jsonrpc', website=True)
    def get_clock_order(self, access_token, config_id, order_access_token, order_id):
        pos_config = self._get_pos_config_force(access_token, config_id)
        order = request.env['pos.order'].sudo().browse(order_id)

        if not order or not consteq(order_access_token, order.access_token):
            return {}

        return self._generate_return_values(order, pos_config)

    def _get_pos_config_force(self, access_token, config_id):
        pos_config_sudo = request.env['pos.config'].sudo().browse(int(config_id))
        if not pos_config_sudo or not consteq(pos_config_sudo.access_token, access_token):
            raise Unauthorized("Invalid Access Token.")
        company = pos_config_sudo.company_id
        user = pos_config_sudo.self_ordering_default_user_id
        return pos_config_sudo.sudo(False).with_company(company).with_user(user).with_context(allowed_company_ids=company.ids)


class BlackboxPosController(PosController):
    @http.route()
    def pos_web(self, config_id=False, from_backend=False, **k):
        config = request.env['pos.config'].sudo().browse(int(config_id))
        if config.current_session_id.state == "opened":
            request.env['pos.blackbox.log.ip']._log_ip(config, None)
        return super().pos_web(config_id=config_id, from_backend=from_backend, **k)
