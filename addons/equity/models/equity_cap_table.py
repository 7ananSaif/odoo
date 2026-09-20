from collections import defaultdict
from datetime import datetime

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools import SQL


class EquityCapTable(models.Model):
    _name = 'equity.cap.table'
    _description = "Cap Table"
    _auto = False

    partner_id = fields.Many2one('res.partner')
    holder_id = fields.Many2one('res.partner')
    security_class_id = fields.Many2one('equity.security.class')

    securities = fields.Float()
    securities_type = fields.Selection(related='security_class_id.class_type')
    votes = fields.Float()

    ownership = fields.Float()
    voting_rights = fields.Float()
    dividend_payout = fields.Float()
    dilution = fields.Float()
    valuation = fields.Float()

    @property
    def _table_query(self):
        self.env['equity.transaction'].flush_model()
        current_date = self.env.context.get('current_date') or datetime.max.date()

        domain = Domain('date', '<=', current_date)
        if current_transaction_id := self.env.context.get('current_transaction_id'):
            domain &= Domain('id', '!=', current_transaction_id)
        transactions_query = self.env['equity.transaction']._search(domain)
        exercise_transactions_query = self.env['equity.transaction']._search(domain & Domain('transaction_type', '=', 'exercise'))
        transfer_transactions_query = self.env['equity.transaction']._search(domain & Domain('transaction_type', '=', 'transfer'))
        all_transactions = SQL(" UNION ALL ").join([
            transactions_query.select(
                'partner_id AS partner_id',
                'subscriber_id AS holder_id',
                'security_class_id AS security_class_id',
                """(CASE
                        WHEN transaction_type IN ('issuance', 'transfer') THEN securities
                        ELSE -securities
                    END) AS securities"""
                ,
            ),
            exercise_transactions_query.select(
                'partner_id AS partner_id',
                'subscriber_id AS holder_id',
                'destination_class_id AS security_class_id',
                'securities AS securities',
            ),
            transfer_transactions_query.select(
                'partner_id AS partner_id',
                'seller_id AS holder_id',
                'security_class_id AS security_class_id',
                '-securities AS securities',
            ),
        ])
        return SQL(
            """
                WITH transactions AS (%(all_transactions)s),
                     security_class AS (
                        SELECT *,
                               CASE WHEN class_type = 'shares' THEN 1 ELSE 0 END AS share_factor,
                               CASE WHEN dividend_payout THEN 1 ELSE 0 END AS dp_factor
                          FROM equity_security_class
                     )
              SELECT CONCAT(partner_id, '-', holder_id, '-', security_class_id, '-', %(current_date)s) AS id,
                     partner_id,
                     holder_id,
                     security_class_id,
                     SUM(securities) AS securities,
                     SUM(securities * security_class.share_votes) AS votes,
                     SUM(securities * security_class.share_factor) / NULLIF(SUM(SUM(securities * security_class.share_factor)) OVER by_partner, 0) AS ownership,
                     SUM(securities * security_class.share_votes) / NULLIF(SUM(SUM(securities * security_class.share_votes)) OVER by_partner, 0) AS voting_rights,
                     SUM(securities * security_class.dp_factor) / NULLIF(SUM(SUM(securities * security_class.dp_factor)) OVER by_partner, 0) AS dividend_payout,
                     SUM(securities) / NULLIF(SUM(SUM(securities)) OVER by_partner, 0) AS dilution,
                     SUM(securities) / NULLIF((SUM(SUM(securities)) OVER by_partner), 0) * last_valuation.valuation AS valuation
                FROM transactions
                JOIN security_class ON security_class.id = transactions.security_class_id
   LEFT JOIN LATERAL (
                        SELECT valuation
                          FROM equity_valuation
                         WHERE partner_id = transactions.partner_id
                           AND date <= %(current_date)s
                      ORDER BY date DESC
                         LIMIT 1
                     ) last_valuation ON TRUE
            GROUP BY partner_id, holder_id, security_class_id, last_valuation.valuation
              WINDOW by_partner AS (PARTITION BY partner_id)
            """,
            all_transactions=all_transactions,
            current_date=current_date,
        )

    def _append_cap_table_entry(self, data, cap_table_entry):
        security_class_id = cap_table_entry.security_class_id.id
        data['classes'][security_class_id] += cap_table_entry.securities

        data['ownership'] += cap_table_entry.ownership
        data['voting_rights'] += cap_table_entry.voting_rights
        data['dividend_payout'] += cap_table_entry.dividend_payout
        data['dilution'] += cap_table_entry.dilution
        data['valuation'] += cap_table_entry.valuation
        return data

    @api.model
    def get_cap_table_data(self, partner_ids):
        # {partner_id: {holder_id: {...}}}
        partner_holder_data = defaultdict(lambda: defaultdict(lambda: {
            'classes': defaultdict(int),
            'ownership': 0,
            'voting_rights': 0,
            'dividend_payout': 0,
            'dilution': 0,
            'valuation': 0,
        }))
        partner_classes_ids = defaultdict(list)
        partner_data = {}
        class_data = {}

        domain = []
        if partner_ids:
            domain.append(('partner_id', 'in', partner_ids))

        for cap_table_entry in self.search(domain):
            partner = cap_table_entry.partner_id
            holder = cap_table_entry.holder_id
            security_class = cap_table_entry.security_class_id

            if partner.id not in partner_data:
                partner_data[partner.id] = partner._get_cap_table_data()
            if holder and holder.id not in partner_data:
                partner_data[holder.id] = holder._get_cap_table_data()

            if security_class.id not in class_data:
                class_data[security_class.id] = security_class._get_cap_table_data()

            if security_class.id not in partner_classes_ids[partner.id]:
                partner_classes_ids[partner.id].append(security_class.id)

            self._append_cap_table_entry(partner_holder_data[partner.id][holder.id], cap_table_entry)

        for partner_id, security_class_ids in partner_classes_ids.items():
            # to have a deterministic order of share classes on the cap table
            partner_classes_ids[partner_id] = self.env['equity.security.class'].browse(security_class_ids).sorted().ids

        return {
            'partner_holder_data': partner_holder_data,
            'partner_classes_ids': partner_classes_ids,
            'partner_data': partner_data,
            'class_data': class_data,
        }

    @api.model
    @api.readonly
    def search(self, domain, offset: int = 0, limit: int | None = None, order: str | None = None):
        # Always fetch all the fields when searching to avoid doing a lookup by id afterwards
        return self.search_fetch(domain, list(self._fields), offset=offset, limit=limit, order=order)
