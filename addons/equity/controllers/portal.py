from functools import partial

from odoo import fields
from odoo.http import request, route
from odoo.tools import format_amount, format_date, consteq
from odoo.addons.base.models.ir_qweb import keep_query
from odoo.addons.equity.utils import safe_division
from odoo.addons.equity.models.equity_ubo import CONTROL_METHODS, ACTIVATE_PERCENTAGES, ACTIVATE_ROLE, AUTH_REP_ROLES
from odoo.addons.portal.controllers.portal import CustomerPortal


class PortalEquity(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'transaction_count' in counters:
            holder_id = self._get_user_partner_id()
            values['transaction_count'] = (
                request.env['equity.transaction'].search_count(self._get_transactions_domain(holder_id), limit=1)
                if holder_id and request.env['equity.transaction'].has_access('read') else
                0
            )
        return values

    def _get_user_partner_id(self, access_token=None, default_to_request_partner=True):
        partner_id, token = None, None
        if access_token and '$' in access_token:
            partner_id, token = access_token.split('$', maxsplit=1)
        if (
            partner_id and
            (partner := request.env['res.partner'].sudo().browse(int(partner_id))) and
            partner.equity_access_token and
            consteq(partner.equity_access_token, token)
        ):
            return int(partner_id)
        elif default_to_request_partner and request.env['equity.transaction'].has_access('read'):
            return request.env.user.partner_id.id
        return False

    def _get_transactions_domain(self, holder_id):
        return [
            '|',
            ('subscriber_id', '=', holder_id),
            ('seller_id', '=', holder_id),
            ('date', '<=', fields.Date.context_today(self)),
        ]

    def _prepare_my_transactions_values(self, partner_id, access_token=None):
        def get_sign(holder_id, transaction):
            sign = -1 if transaction.transaction_type == 'cancellation' else 1
            if transaction.seller_id.sudo().id == holder_id:
                sign = -1  # seller always loses shares
            return sign

        EquityTransaction = request.env['equity.transaction'].sudo()
        holder_id = self._get_user_partner_id(access_token)
        if not holder_id:
            raise request.not_found()
        partner_sudo = request.env['res.partner'].sudo().browse(int(partner_id))
        transaction_type_dict = dict(EquityTransaction._fields['transaction_type']._description_selection(request.env))

        transactions = EquityTransaction.search([
            ('partner_id', '=', partner_id),
            *self._get_transactions_domain(holder_id),
        ], order='date')

        if not len(transactions):
            raise request.not_found()

        today = fields.Date.context_today(self)

        transactions_events = [
            {
                'is_exercise': (is_exercise := transaction.transaction_type == 'exercise'),
                'is_options_issuance': (is_options_issuance := transaction.transaction_type == 'issuance' and transaction.securities_type == 'options'),
                'date': transaction.date,
                'expiration_date': transaction.expiration_date if is_options_issuance else '',
                'event': transaction_type_dict.get(transaction.transaction_type),
                'security_class': transaction.security_class_id.name + ('' if not is_exercise else f' → {transaction.destination_class_id.name}'),
                'securities': (securities := transaction.securities * get_sign(holder_id, transaction)),
                'security_price': transaction.security_price,
                'transaction_price': securities * (1 if is_options_issuance else -1) * transaction.security_price,
            } for transaction in transactions
        ]
        transactions_events.append({
            'add_total_tooltip': True,
            'event': request.env._("Total"),
            'securities': sum(event['securities'] for event in transactions_events if not event['is_exercise']),
            'transaction_price': sum(event['transaction_price'] for event in transactions_events if not event['is_options_issuance']),
        })

        valuations = request.env['equity.valuation'].sudo().search([('partner_id', '=', partner_id), ('date', '<=', today)], order='date DESC')

        def chart_data_function(past_date):
            cap_table_entries = request.env['equity.cap.table'].sudo().with_context(current_date=past_date).search([('partner_id', '=', partner_id)])
            holder_cap_table_entries = cap_table_entries.filtered(lambda cte: cte.holder_id.id == holder_id)
            shares = sum(holder_cap_table_entries.filtered(lambda cte: cte.securities_type == 'shares').mapped('securities'))
            total_shares = sum(cap_table_entries.filtered(lambda cte: cte.securities_type == 'shares').mapped('securities'))
            past_valuations = valuations.filtered(lambda v: v.date <= past_date)
            valuation = past_valuations[0].valuation if past_valuations else 0
            return [
                valuation * safe_division(shares, total_shares),
                valuation,
            ]

        cap_table_entries = request.env['equity.cap.table'].sudo().search([('partner_id', '=', partner_id)])
        holder_cap_table_entries = cap_table_entries.filtered(lambda cte: cte.holder_id.id == holder_id)
        shares = sum(holder_cap_table_entries.filtered(lambda cte: cte.securities_type == 'shares').mapped('securities'))
        votes = sum(holder_cap_table_entries.mapped('votes'))
        total_shares = sum(cap_table_entries.filtered(lambda cte: cte.securities_type == 'shares').mapped('securities'))
        total_votes = sum(cap_table_entries.mapped('votes'))
        reported_valuation = valuations[0].valuation if valuations else 0

        return {
            **self._prepare_portal_layout_values(),
            'fmt_amount': partial(format_amount, request.env, currency=partner_sudo.equity_currency_id),
            'fmt_date': partial(format_date, request.env),
            'page_name': 'equity',
            'partner_id': partner_id,
            'holder_id': holder_id,
            'partner_name': partner_sudo.display_name,
            'transactions': transactions_events,
            'chart_props': {
                'labels': [
                    request.env._("Your Value ND"),
                    request.env._("Total Value"),
                ],
                'data': request.env['equity.valuation'].get_valuation_chart_data(data_function=chart_data_function),
                'stats': {
                    'valuation': reported_valuation,
                    'yourValuation': reported_valuation * safe_division(shares, total_shares),
                    'ownership': safe_division(shares, total_shares),
                    'votingRights': safe_division(votes, total_votes),
                    'currencyId': partner_sudo.equity_currency_id.id,
                },
            },
        }

    def _prepare_my_companies_values(self, access_token=None):
        values = self._prepare_portal_layout_values()

        EquityTransaction = request.env['equity.transaction'].sudo()
        holder_id = self._get_user_partner_id(access_token)
        if not holder_id:
            raise request.not_found()

        domain = self._get_transactions_domain(holder_id)
        partners = EquityTransaction.search(domain).partner_id
        securities_per_partner = dict(request.env['equity.cap.table'].sudo()._read_group(
            domain=[('partner_id', 'in', partners.ids), ('holder_id', '=', holder_id)],
            groupby=['partner_id'],
            aggregates=['securities:sum'],
        ))
        values.update({
            'partners': [
                {
                    'id': partner.id,
                    'display_name': partner.display_name,
                    'securities': securities_per_partner.get(partner, 0),
                } for partner in partners
            ],
            'page_name': 'equity',
        })
        return values

    def _prepare_contact_values(self, user_id=None):
        if not user_id:
            return {}
        return request.env['res.users'].sudo().browse(int(user_id)).read(['name', 'email', 'phone'])[0]

    @route('/my/equity/<int:partner_id>', type='http', auth='public', website=True, sitemap=False)
    def portal_my_company_equity(self, partner_id, access_token=None, **kw):
        values = self._prepare_my_transactions_values(partner_id, access_token=access_token)
        return request.render('equity.portal_my_company_equity', values)

    @route('/my/equity', type='http', auth='public', website=True, sitemap=False)
    def portal_my_equity(self, access_token=None, **kw):
        values = self._prepare_my_companies_values(access_token=access_token)
        return request.render('equity.portal_my_equity', values)

    @route('/my/ubo', type='http', auth='public', website=True, sitemap=False)
    def portal_my_ubo(self, access_token=None, user_id=None, **kw):
        values = self._prepare_portal_layout_values()
        partner_id = self._get_user_partner_id(access_token, default_to_request_partner=False)
        if not partner_id:
            raise request.not_found()

        partner_sudo = request.env['res.partner'].sudo().browse(partner_id)
        if not partner_sudo._can_fill_ubo_portal_form():
            return request.redirect(f'/my/ubo/submit?{keep_query()}')

        ubos = request.env['equity.ubo'].sudo().search([('partner_id', '=', partner_id)])
        values.update({
            'access_token': access_token,
            'contact': self._prepare_contact_values(user_id),
            'equity_ubo_settings': {
                'control_methods': dict(CONTROL_METHODS),
                'activate_percentages': ACTIVATE_PERCENTAGES,
                'activate_role': ACTIVATE_ROLE,
                'auth_rep_roles': dict(AUTH_REP_ROLES),
            },
            'all_countries': request.env['res.country'].sudo().search_fetch([], ['id', 'name']).read(['name']),
            'partner': partner_sudo.read(['name', 'vat', 'country_id'], load=None)[0],
            'ubos': [
                {
                    'id': ubo.id,
                    'control_method': ubo.control_method,
                    'ownership': ubo.ownership,
                    'voting_rights': ubo.voting_rights,
                    'auth_rep_role': ubo.auth_rep_role,
                    'start_date': fields.Date.to_string(ubo.start_date),
                    'end_date': fields.Date.to_string(ubo.end_date),
                    'attachment_expiration_date': fields.Date.to_string(ubo.attachment_expiration_date),
                    'holder_id': {
                        'id': ubo.holder_id.id,
                        'name': ubo.holder_id.name,
                        'country_id': ubo.holder_id.country_id.id,
                        'ubo_birth_date': fields.Date.to_string(ubo.holder_id.ubo_birth_date),
                        'ubo_national_identifier': ubo.holder_id.ubo_national_identifier,
                        'ubo_pep': ubo.holder_id.ubo_pep,
                    },
                } for ubo in ubos
            ],
        })
        return request.render('equity.portal_ubo_form', values)

    @route('/my/ubo/submit/data', type='jsonrpc', auth='public')
    def submit_ubo_form_data(self, access_token, data):
        """
            :param data: list of new or existing (if has an id) equity.ubo dicts with a holder_id sub-record dict.
                Each record may have `attachment` which holds a file that should be uploaded to the record chatter.
        """
        partner_id = self._get_user_partner_id(access_token, default_to_request_partner=False)
        if not partner_id:
            return {'error': request.env._("Invalid token")}

        return request.env['equity.ubo'].sudo().submit_ubo_form_data(partner_id, data)

    @route('/my/ubo/submit', type='http', methods=['GET', 'POST'], auth='public', website=True, sitemap=False)
    def portal_my_ubo_submit(self, access_token=None, user_id=None, rep_name=None, rep_position=None, **kw):
        partner_id = self._get_user_partner_id(access_token, default_to_request_partner=False)
        if not partner_id:
            raise request.not_found()
        elif rep_name and rep_position:
            request.env['res.partner'].browse(partner_id)._ubo_portal_form_filled(rep_name=rep_name, rep_position=rep_position)

        values = {
            **self._prepare_portal_layout_values(),
            'contact': self._prepare_contact_values(user_id),
        }
        return request.render('equity.portal_ubo_submit', values)
