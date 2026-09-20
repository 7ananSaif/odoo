# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from odoo.tools.translate import _
from odoo.service.common import exp_version
from uuid import uuid4


class PosConfig(models.Model):
    _inherit = "pos.config"

    iface_fiscal_data_module = fields.Many2one(
        "iot.device",
        domain=lambda self: ['&', ('type', '=', 'fiscal_data_module'), '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)],
    )
    certified_blackbox_identifier = fields.Char(
        "Blackbox Identifier",
        store=True,
        compute="_compute_certified_pos",
        readonly=True,
    )
    pos_version = fields.Char('Odoo Version', compute='_compute_odoo_version')

    def _compute_odoo_version(self):
        self.pos_version = exp_version()['server_serie']

    @api.model
    def _load_pos_data_read(self, records, config):
        read_records = super()._load_pos_data_read(records, config)
        if read_records and config.certified_blackbox_identifier:
            record = read_records[0]
            record["_product_product_work_in"] = self.env.ref("pos_blackbox_be.product_product_work_in").id
            record["_product_product_work_out"] = self.env.ref("pos_blackbox_be.product_product_work_out").id
        return read_records

    @api.depends("iface_fiscal_data_module")
    def _compute_certified_pos(self):
        for config in self:
            if config.iface_fiscal_data_module:
                config.certified_blackbox_identifier = config.iface_fiscal_data_module.name[
                    -14:
                ]
                self.env["pos_blackbox_be.log"].sudo().create([{
                    "action": "create",
                    "model_name": config._name,
                    "record_name": config.name,
                    "description": "Session started with: %s" % config.certified_blackbox_identifier,
                }])
                if not self.env['ir.sequence'].search([('code', '=', f'pos_blackbox_be.NS_blackbox_{config.certified_blackbox_identifier}')]):
                    self.env['ir.sequence'].sudo().create({
                        'name': _("NS Order by blackbox"),
                        'padding': 4,
                        'code': f'pos_blackbox_be.NS_blackbox_{config.certified_blackbox_identifier}',
                        'company_id': False,
                    })
                    self.env['ir.sequence'].sudo().create({
                        'name': _("PS Order by blackbox"),
                        'padding': 4,
                        'code': f'pos_blackbox_be.PS_blackbox_{config.certified_blackbox_identifier}',
                        'company_id': False,
                    })

    def write(self, vals):
        if (vals.get('iface_fiscal_data_module') or self.certified_blackbox_identifier):
            cash_rounding = self._create_default_cashrounding()
            if cash_rounding:
                vals['cash_rounding'] = True
                vals['rounding_method'] = cash_rounding.id
                vals['only_round_cash_method'] = True
            vals['iface_print_auto'] = True
            vals['iface_print_skip_screen'] = True
        return super().write(vals)

    def _check_is_certified_pos(self):
        action = self.env['pos.config'].action_pos_config_modal_edit()
        action['res_id'] = self.id

        fdm_required = self.certified_blackbox_identifier or self.env['pos.config'].search_count(
            domain=[
                *self.env['account.journal']._check_company_domain(self.company_id),
                ('certified_blackbox_identifier', '!=', False),
            ],
            limit=1
        )

        fdm_ids = self.env['iot.device'].search([
            *self.env['iot.device']._check_company_domain(self.company_id),
            ('type', '=', 'fiscal_data_module'),
        ], limit=2)

        if not self.iface_fiscal_data_module and fdm_required:
            self.is_posbox = True
            if len(fdm_ids) != 1:
                action['context']['fdm_required'] = True
                return action
            self.iface_fiscal_data_module = fdm_ids[0]   # If only one FDM is available, set it automatically

        return False

    @api.depends("iface_fiscal_data_module")
    def _compute_iot_device_ids(self):
        super()._compute_iot_device_ids()
        for config in self:
            if config.is_posbox:
                config.iot_device_ids += config.iface_fiscal_data_module

    def _action_to_open_ui(self):
        res = super()._action_to_open_ui()
        if self.current_session_id.state == "opened":
            self.env['pos.blackbox.log.ip']._log_ip(self, None)
        return res

    def _check_before_creating_new_session(self):
        res = self._check_is_certified_pos()
        if res:
            return res
        if self.iface_fiscal_data_module:
            self._check_loyalty()
            res = self._check_insz_user() or self._check_company_address() or self._check_printer_connected()
            if res:
                return res
            self._check_work_product_taxes_and_categories()
            self._check_employee_insz_or_bis_number()
            self._check_cash_rounding()
        return super()._check_before_creating_new_session()

    def _check_loyalty(self):
        for config in self:
            if self.env['ir.module.module'].search([('name', '=', 'pos_loyalty'), ('state', '=', 'installed')]) and len(config._get_program_ids().filtered(lambda p: p.company_id == config.company_id)) > 0:
                raise UserError(
                    _(
                        "Loyalty programs and gift card cannot be used on a PoS associated with a blackbox."
                    )
                )

    def _check_work_product_taxes_and_categories(self):
        work_products = self._get_work_products()
        for work_product in work_products:
            if not work_product.available_in_pos:
                raise ValidationError(
                    _("The WORK IN/OUT products must be available in the POS.")
                )
            if (
                not work_product.taxes_id
                or any(t.amount != 0 for t in work_product.taxes_id)
            ):
                raise ValidationError(
                    _("The WORK IN/OUT products must have a taxes with 0%.")
                )
            if (len(work_product.pos_categ_ids) != 1):
                raise ValidationError(
                    _("The WORK IN/OUT products must have one and only one POS category. We advise you to use the POS category named 'Fiscal category'.")
                )
        if (len(work_products.pos_categ_ids) != 1):
            raise ValidationError(
                _("The WORK IN/OUT products must have the same POS category. We advise you to use the POS category named 'Fiscal category'.")
            )

    def _check_insz_user(self):
        if not self.env.user.insz_or_bis_number:
            action = self.env['ir.actions.actions']._for_xml_id('base.action_res_users')
            action['res_id'] = self.env.user.id
            action['views'] = [[self.env.ref('base.view_users_form').id, 'form']]
            action['target'] = 'new'
            action['context'] = {
                'insz_required': True,
            }
            return action
        return False

    def _check_company_address(self):
        if not self.company_id.street or not self.company_id.company_registry:
            action = self.env['ir.actions.actions']._for_xml_id('base.action_res_company_form')
            action['res_id'] = self.company_id.id
            action['views'] = [[self.env.ref('base.view_company_form').id, 'form']]
            action['target'] = 'new'
            action['context'] = {
                'company_address_required': not self.company_id.street,
                'company_vat_required': not self.company_id.company_registry,
            }
            return action
        return False

    @api.constrains("iface_fiscal_data_module", "fiscal_position_ids")
    def _check_posbox_fp_tax_code(self):
        invalid_tax_lines = [
            (fp.name, tax.name)
            for config in self
            for fp in config.fiscal_position_ids
            for tax in fp.tax_ids
            if (
                not tax.tax_group_id.pos_receipt_label
                and any(tax.original_tax_ids.tax_group_id.mapped('pos_receipt_label'))
            )
        ]

        if invalid_tax_lines:
            raise ValidationError(_("Fiscal Position %(fp_name)s (tax %(tax_dest_name)s) has an invalid tax amount. Only 21%%, 12%%, 6%% and 0%% are allowed.", fp_name=invalid_tax_lines[0][0], tax_dest_name=invalid_tax_lines[0][1]))

    def _check_employee_insz_or_bis_number(self):
        for config in self:
            if config.module_pos_hr:
                all_employee_ids = self.env['hr.employee'].search(self._employee_domain(self.env.uid))
                comp_user = self.env.user.with_company(self.company_id)
                emp_names = [emp.name for emp in all_employee_ids if not emp.sudo().insz_or_bis_number] + ([comp_user.name] if not comp_user.employee_id.sudo().insz_or_bis_number else [])

                if len(emp_names) > 0:
                    raise ValidationError(
                        _("%s must have an National Register Number.", ", ".join(emp_names))
                    )

    def _check_cash_rounding(self):
        if self.payment_method_ids.filtered(lambda p: p.is_cash_count):
            if not self.cash_rounding:
                raise ValidationError(_("Cash rounding must be enabled"))
            if (
                self.rounding_method.rounding != 0.05
                or self.rounding_method.rounding_method != "HALF-UP"
            ):
                raise ValidationError(
                    _('The rounding method must be set to 0.05 and "Nearest"')
                )

    def _check_printer_connected(self):
        epson_printer = False
        if hasattr(self, "epson_printer_ip"):
            epson_printer = self.epson_printer_ip
        if not self.iface_printer_id and not epson_printer:
            action = self.env['pos.config'].action_pos_config_modal_edit()
            action['res_id'] = self.id
            action['context'].update({'printer_required': True})
            return action
        if not self.iface_print_auto:
            raise ValidationError(_("Automatic Receipt Printing must be activated"))
        if not self.iface_print_skip_screen:
            raise ValidationError(_("Skip Preview Screen must be activated"))
        return False

    def _get_work_products(self):
        empty_product = self.env['product.product']
        work_in_product = self.env.ref('pos_blackbox_be.product_product_work_in', raise_if_not_found=False) or empty_product
        work_out_product = self.env.ref('pos_blackbox_be.product_product_work_out', raise_if_not_found=False) or empty_product
        return work_in_product | work_out_product

    def _get_special_products(self):
        return super()._get_special_products() | self._get_work_products()

    def get_NS_sequence_next(self):
        return self.env['ir.sequence'].next_by_code(f'pos_blackbox_be.NS_blackbox_{self.certified_blackbox_identifier}')

    def get_PS_sequence_next(self):
        return self.env['ir.sequence'].next_by_code(f'pos_blackbox_be.PS_blackbox_{self.certified_blackbox_identifier}')

    @api.model
    def _create_default_cashrounding(self):
        cash_rounding = self.env.ref('pos_blackbox_be.default_l10n_be_cash_rounding', raise_if_not_found=False)
        if cash_rounding:
            return cash_rounding
        if self.env.company.chart_template == "be_comp":
            profit_account = self.env.ref(f'account.{self.env.company.id}_a743', raise_if_not_found=False)
            loss_account = self.env.ref(f'account.{self.env.company.id}_a643', raise_if_not_found=False)
            if profit_account and loss_account:
                cash_rounding = self.env['account.cash.rounding'].create({
                    'name': _('Belgian Cash Rounding'),
                    'rounding_method': 'HALF-UP',
                    'rounding': 0.05,
                    'profit_account_id': profit_account.id,
                    'loss_account_id': loss_account.id,
                })
                self.env['ir.model.data']._update_xmlids([
                    {
                        'xml_id': 'pos_blackbox_be.default_l10n_be_cash_rounding',
                        'record': cash_rounding,
                        'noupdate': True,
                    }
                ])
            return cash_rounding
        return False

    @api.model
    def _send_order_to_blackbox(self, order, clock=False, clock_in=True):
        iface_fiscal_data_module = order.config_id.iface_fiscal_data_module
        blackbox_data = order._create_order_for_blackbox(clock, clock_in)
        message = {
            "iot_identifiers": [iface_fiscal_data_module.iot_id.identifier],
            "device_identifiers": [iface_fiscal_data_module.identifier],
            "action": "registerReceiptWeb",
            "high_level_message": blackbox_data,
            "id": order.id,
        }
        self.env['iot.channel'].send_message(message)
        return True

    def _clock_kiosk_user(self, clock_in):
        pos_reference, _ = self._get_next_order_refs()
        clock_order = self.env['pos.order'].create({
            'session_id': self.current_session_id.id,
            'company_id': self.company_id.id,
            'config_id': self.id,
            'user_id': self.current_user_id.id,
            'access_token': str(uuid4()),
            'pos_reference': pos_reference,
            'amount_tax': 0,
            'amount_total': 0,
            'amount_paid': 0,
            'amount_return': 0,
            'lines': [(0, 0, {
                'name': 'Work in' if clock_in else 'Work out',
                'product_id': self.env.ref('pos_blackbox_be.product_product_work_in').id if clock_in else self.env.ref('pos_blackbox_be.product_product_work_out').id,
                'price_subtotal': 0,
                'price_subtotal_incl': 0,
                'tax_ids': [(6, 0, self.env.ref('pos_blackbox_be.product_product_work_in').taxes_id.ids)],
                'qty': 1,
            })]
        })
        clock_order.action_pos_order_paid()
        self._send_order_to_blackbox(clock_order, True, clock_in)

    def action_close_kiosk_session(self):
        if self.certified_blackbox_identifier:
            self._clock_kiosk_user(False)
        return super().action_close_kiosk_session()
