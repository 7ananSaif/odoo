import base64
from dateutil.relativedelta import relativedelta
import json
import uuid
from werkzeug.urls import url_encode

from odoo import api, fields, models
from odoo.tools.misc import format_date, format_decimalized_amount


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    equity_access_token = fields.Char(groups=fields.NO_ACCESS, prefetch=False, copy=False)

    # Investee (Company) fields
    equity_transaction_ids = fields.One2many('equity.transaction', 'partner_id')
    equity_transaction_count = fields.Integer(compute='_compute_transaction_count')
    equity_currency_id = fields.Many2one('res.currency', string="Equity Currency", default=lambda self: self.env.company.currency_id)

    equity_shareholders_count = fields.Integer(compute='_compute_shareholders_count')

    equity_valuation_ids = fields.One2many('equity.valuation', 'partner_id')
    equity_last_valuation = fields.Char(compute='_compute_equity_last_valuation')
    equity_kanban_dashboard_graph = fields.Text(compute='_compute_equity_kanban_dashboard_graph')

    equity_legal_form = fields.Char(string="Legal Form")
    equity_formation_date = fields.Date(string="Formation Date")

    # Ultimate Beneficial Owner
    ubo_birth_date = fields.Date(string="Birth Date")
    ubo_birth_place = fields.Char(string="Birth Place")
    ubo_national_identifier = fields.Char(string="UBO ID Number")
    ubo_pep = fields.Boolean(string="PEP", help="Politically Exposed Person")

    ubo_owner_ids = fields.One2many('equity.ubo', 'partner_id')
    ubo_owned_company_ids = fields.One2many('equity.ubo', 'holder_id')

    # Investee (Company) methods
    def _compute_transaction_count(self):
        partners_transactions = dict(self.env['equity.transaction']._read_group(
            domain=[('partner_id', 'in', self.ids)],
            groupby=['partner_id'],
            aggregates=['__count'],
        ))
        for partner in self:
            partner.equity_transaction_count = partners_transactions.get(partner, 0)

    def _compute_shareholders_count(self):
        partners_holders = dict(self.env['equity.cap.table']._read_group(
            domain=[('partner_id', 'in', self.ids)],
            groupby=['partner_id'],
            aggregates=['holder_id:count_distinct'],
        ))
        for partner in self:
            partner.equity_shareholders_count = partners_holders.get(partner, 0)

    def _compute_equity_last_valuation(self):
        for partner in self:
            last_valuation_id = self.env['equity.valuation'].search([('partner_id', '=', partner.id), ('date', '<=', fields.Date.today())], order='date DESC', limit=1)
            partner.equity_last_valuation = format_decimalized_amount(0 if not last_valuation_id else last_valuation_id.valuation, partner.equity_currency_id)

    def _compute_equity_kanban_dashboard_graph(self):
        for partner in self:
            partner_valuations = self.env['equity.valuation'].search([('partner_id', '=', partner.id)], order='date ASC')
            values = [
                {
                    'x': format_date(self.env, partner_valuations[0].date - relativedelta(days=1), date_format='d LLLL Y'),
                    'y': 0,
                },
                *[
                    {
                        'x': format_date(self.env, partner_valuation.date, date_format='d LLLL Y'),
                        'y': partner_valuation.valuation,
                    } for partner_valuation in partner_valuations
                ],
            ] if partner_valuations else [{
                'x': '',
                'y': (2 ** i) - 1,
            } for i in range(6)]
            partner.equity_kanban_dashboard_graph = json.dumps([{
                'values': values,
                'title': '',
                'key': self.env._("Valuation"),
                'is_sample_data': not len(partner_valuations),
            }])

    # cap table methods
    def _get_cap_table_data(self):
        self.ensure_one()
        return {
            'display_name': self.display_name,
            'equity_currency_id': self.equity_currency_id.id,
        }

    @api.model
    def open_equity_dashboard(self):
        partners_with_transactions = self.search([('equity_transaction_ids', '!=', False)], limit=2)
        if len(partners_with_transactions) <= 1:
            return partners_with_transactions.action_open_cap_table()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Equity"),
            'res_model': 'res.partner',
            'views': [(self.env.ref('equity.equity_dashboard_res_partner').id, 'kanban')],
            'domain': [('equity_transaction_ids', '!=', False)],
        }

    def action_open_cap_table(self):
        return {
            **self.env['ir.actions.actions']._for_xml_id('equity.action_equity_cap_table'),
            'display_name': self.env._("Cap Table"),
            'context': {
                'active_ids': self.ids,
            },
        }

    def action_open_valuation_list(self):
        self.ensure_one()
        return self.equity_valuation_ids._get_records_action(
            display_name=self.env._("%(partner_name)s's Valuations", partner_name=self.display_name),
            context={
                'default_partner_id': self.id,
            },
        )

    def action_open_transaction_list(self):
        self.ensure_one()
        return self.equity_transaction_ids._get_records_action(
            display_name=self.env._("%(partner_name)s's Transactions", partner_name=self.display_name),
            context={
                'default_partner_id': self.id,
            },
        )

    # misc methods
    def _equity_ensure_token(self):
        """ Get the current record equity access token """
        if not self.equity_access_token:
            # we use a `write` to force the cache clearing otherwise `return self.access_token` will return False
            self.sudo().write({'equity_access_token': str(uuid.uuid4())})
        return f"{self.id}${self.equity_access_token}"

    def _get_equity_url_params(self):
        self.ensure_one()
        return url_encode({
            'access_token': self.sudo()._equity_ensure_token(),
            'user_id': self.env.user.id,
        })

    def _ubo_portal_form_filled(self, rep_name, rep_position):
        self.ensure_one()
        sudo_self = self.sudo()
        if ubo_activities := sudo_self.activity_search(['equity.equity_ubo_form_mail_activity']):
            last_ubo_activity = ubo_activities[-1]
        else:
            return

        pdf_content, _ = sudo_self.env['ir.actions.report']._render_qweb_pdf(
            'equity.equity_ubo_report',
            res_ids=[self.id],
            data={'rep_name': rep_name, 'rep_position': rep_position, 'rep_sig_date': fields.Date.today()},
        )
        attachment = sudo_self.env['ir.attachment'].create({
            'name': 'UBO_report.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'res.partner',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        last_ubo_activity.with_user(self.env.ref('base.user_root')).action_feedback(feedback=self.env._("(Completed through portal Form)"), attachment_ids=[attachment.id])

    def _can_fill_ubo_portal_form(self):
        self.ensure_one()
        ubo_activities = self.sudo().activity_search(['equity.equity_ubo_form_mail_activity'])
        return bool(ubo_activities)

    def _message_mail_after_hook(self, mails):
        if self.env.context.get('create_ubo_to_do_activity'):
            ubo_activity_xml_id = 'equity.equity_ubo_form_mail_activity'
            date_deadline = fields.Date.context_today(self) + relativedelta(days=7)
            self.activity_reschedule(
                act_type_xmlids=[ubo_activity_xml_id],
                date_deadline=date_deadline,
            ) or self.activity_schedule(
                act_type_xmlid=ubo_activity_xml_id,
                summary=self.env._("Upload UBO Form"),
                note=self.env._("UBO portal form will become unavailable once this activity will be marked as done"),
                date_deadline=date_deadline,
                user_id=self.env.user.id,
            )
        return super()._message_mail_after_hook(mails)

    def _get_ubo_report_filename(self):
        self.ensure_one()
        return "%s_ubo.pdf" % self.display_name.replace(' ', '_')

    def action_partner_equity_send(self, linked_transaction=None):
        self.ensure_one()
        linked_transaction = linked_transaction or self.env['equity.transaction'].search([
            ('date', '<=', fields.Date.context_today(self)),
            '|', ('subscriber_id', '=', self.id), ('seller_id', '=', self.id),
        ], order='date DESC', limit=1)
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Invite %s", self.name),
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'view_id': self.env.ref('equity.equity_email_compose_message_wizard_form').id,
            'target': 'new',
            'context': {
                'default_model': 'equity.transaction',
                'default_res_ids': linked_transaction.ids,
                'default_partner_ids': self.ids,
                'default_template_id': self.env.ref('equity.equity_shareholder_email_template').id,
                'default_composition_mode': 'comment',
                'hide_recipients': True,
                'holder_name': self.name,
                'equity_access_token': self.sudo()._equity_ensure_token(),
            },
        }
