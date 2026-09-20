# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import api, fields, models


class SaleCommissionAchievementReport(models.Model):
    _inherit = "sale.commission.achievement.report"

    @api.model
    def _get_subscription_currency_rates(self):
        """ Get a query to be able to convert the MRR log amount (in SO currency) to the currency of the current company.
        This method uses the same logic than sale.order.log.report.
        """
        conversion_date = fields.Date.today()
        # In case we want to replay data at previous date
        if self.env.context.get('conversion_date'):
            conversion_date = datetime.strptime(self.env.context['conversion_date'], '%Y-%m-%d')
        query = f"""
            sub_rate_query AS(
                SELECT
                        rc.id AS currency_id,
                        rc.name,
                        rcr.company_id,
                        (array_agg(rcr.name order by rcr.name desc))[1] as date,
                        (array_agg(rcr.rate order by rcr.name desc))[1] as rate
                  FROM res_currency rc
                  JOIN res_currency_rate rcr
                    ON rcr.currency_id = rc.id
                 WHERE rc.active
                   AND rcr.name <= '{conversion_date}'
              GROUP BY rc.id, rc.name, rcr.company_id
        ),
        """
        return query

    @api.model
    def _get_filtered_order_log_cte(self, users=None, teams=None):
        date_from, date_to = self._get_achievement_default_dates()
        today = fields.Date.today().strftime('%Y-%m-%d')
        query = f"""
        filtered_order_logs AS (
            SELECT
                    l.id,
                    l.order_id,
                    l.plan_id,
                    l.amount_signed,
                    l.team_id,
                    l.company_id,
                    l.user_id,
                    l.currency_id,
                    l.event_date,
                    l.effective_date,
                    l.create_date
              FROM sale_order_log l
             WHERE 1=1
               {'AND l.user_id in (%s)' % ','.join(str(i) for i in users.ids) if users else ''}
               {'AND l.team_id in (%s)' % ','.join(str(i) for i in teams.ids) if teams else ''}
               {"AND l.event_date >= '%s' " % datetime.strftime(date_from, "%Y-%m-%d") if date_from else ''}
               AND l.event_date <= '{datetime.strftime(date_to, "%Y-%m-%d") if date_to else today}'
        ),
        """
        return query

    @api.model
    def _get_sale_order_log_rates(self):
        return ['mrr']

    @api.model
    def _get_sale_order_log_product(self):
        # TODO BIG CURRENCY CHANGES 0_0
        return """
            rules.mrr_rate * log.amount_signed /  log_rate.rate
        """

    @api.model
    def _select_rules(self):
        res = super()._select_rules()
        res += """
        ,scpa.recurring_plan_id
        """
        return res

    @api.model
    def _join_invoices(self, join_type=None):
        res = super()._join_invoices(join_type=join_type)
        res += """
          LEFT JOIN sale_order sub ON sub.id=aml.subscription_id
        """
        return res

    @api.model
    def _where_invoices(self):
        res = super()._where_invoices()
        # When the rules has no recurring plan, all invoices match, otherwise only the plan of the subscription
        res += """
          AND ((rules.recurring_plan_id IS NULL) OR (rules.recurring_plan_id=sub.plan_id))
        """
        return res

    def _subscription_lines(self, users=None, teams=None):
        return f"""
{self._get_subscription_currency_rates()}
{self._get_filtered_order_log_cte(users=users, teams=teams)}
subscription_rules AS (
    SELECT
        COALESCE(scpu.date_from, scp.date_from) AS date_from,
        COALESCE(scpu.date_to, scp.date_to) AS date_to,
        scpu.user_id AS user_id,
        scp.team_id AS team_id,
        scp.id AS plan_id,
        scpa.recurring_plan_id,
        scp.company_id,
        scp.currency_id AS currency_to,
        scp.user_type = 'team' AS team_rule,
        {self._rate_to_case(self._get_sale_order_log_rates())}
    FROM sale_commission_plan_achievement scpa
    JOIN sale_commission_plan scp ON scp.id = scpa.plan_id
    JOIN sale_commission_plan_user scpu ON scpa.plan_id = scpu.plan_id
    WHERE scp.state = 'approved'
      AND scp.active
      AND scpa.type IN ({','.join("'%s'" % r for r in self._get_sale_order_log_rates())})
    {'AND scpu.user_id in (%s)' % ','.join(str(i) for i in users.ids) if users else ''}
), subscription_commission_lines_team AS (
    SELECT
        rules.user_id,
        MAX(log.team_id) AS team_id,
        rules.plan_id,
        SUM({self._get_sale_order_log_product()}) AS achieved,
        log.currency_id AS currency_id,
        MAX(log.event_date) AS date,
        MAX(rules.company_id) AS plan_company_id,
        MAX(log.company_id) AS achievement_company_id,
        MAX(log.order_id) AS related_res_id,
        MAX(so.partner_id) AS partner_id,
        -- create_date because _update_effective_date could update several logs at the same time
        -- transfers are created in the same transaction, we need to distinguish them too.
        -- We do it based on there id, generally they have very close id so modulo 10 is enough
        MAX(log.create_date) + (MAX(log.id) % 10) * INTERVAL '1 minute' AS entropy_date

    FROM subscription_rules rules
    JOIN filtered_order_logs log ON log.team_id=rules.team_id
    JOIN sale_order so ON so.id = log.order_id
    JOIN sub_rate_query log_rate ON log_rate.currency_id=log.currency_id AND log_rate.company_id=log.company_id
    WHERE rules.team_rule
      AND (rules.recurring_plan_id IS NULL OR log.plan_id = rules.recurring_plan_id)
      AND log.team_id = rules.team_id
    {'AND log.team_id in (%s)' % ','.join(str(i) for i in teams.ids) if teams else ''}
      AND log.event_date BETWEEN rules.date_from AND rules.date_to
      AND log.effective_date IS NOT NULL
    GROUP BY
        log.id,
        rules.plan_id,
        rules.user_id,
        log.currency_id
), subscription_commission_lines_user AS (
    SELECT
        rules.user_id,
        MAX(log.team_id) AS team_id,
        rules.plan_id,
        SUM({self._get_sale_order_log_product()}) AS achieved,
        log.currency_id AS currency_id,
        MAX(log.event_date) AS date,
        MAX(rules.company_id) AS plan_company_id,
        MAX(log.company_id) AS achievement_company_id,
        MAX(log.order_id) AS related_res_id,
        MAX(so.partner_id) AS partner_id,
        -- create_date because _update_effective_date could update several logs at the same time
        -- transfers are created in the same transaction, we need to distinguish them too.
        -- We do it based on there id, generally they have very close id so modulo 10 is enough
        MAX(log.create_date) + (MAX(log.id) % 10) * INTERVAL '1 minute' AS entropy_date

    FROM subscription_rules rules
        JOIN filtered_order_logs log ON log.user_id=rules.user_id
    JOIN sale_order so ON so.id = log.order_id
    JOIN sub_rate_query log_rate ON log_rate.currency_id=log.currency_id AND log_rate.company_id=log.company_id
    WHERE NOT rules.team_rule
      AND (rules.recurring_plan_id IS NULL OR log.plan_id = rules.recurring_plan_id)
      AND log.user_id = rules.user_id
    {'AND log.user_id in (%s)' % ','.join(str(i) for i in users.ids) if users else ''}
      AND log.event_date BETWEEN rules.date_from AND rules.date_to
      AND log.effective_date IS NOT NULL
    GROUP BY
        log.id,
        rules.plan_id,
        rules.user_id,
        log.currency_id
), subscription_commission_lines AS (
    (SELECT *, 'sale.order' AS related_res_model FROM subscription_commission_lines_team)
    UNION ALL
    (SELECT *, 'sale.order' AS related_res_model FROM subscription_commission_lines_user)
)""", 'subscription_commission_lines'

    def _commission_lines_cte(self, users=None, teams=None):
        return super()._commission_lines_cte(users, teams) + [self._subscription_lines(users, teams)]
