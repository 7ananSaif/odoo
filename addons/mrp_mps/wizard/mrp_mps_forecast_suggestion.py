from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_date
from odoo.tools.float_utils import float_round


class MrpMpsForecastSuggestion(models.TransientModel):
    _name = 'mrp.mps.forecast.suggestion'
    _description = "Forecast Demand Suggestion"

    mrp_mps_id = fields.Many2one('mrp.production.schedule')
    product_id = fields.Many2one('product.product', related='mrp_mps_id.product_id', readonly=True)
    period = fields.Integer(string='Period')
    based_on = fields.Selection(
        [('actual_demand', 'Actual Demand'),
         ('last_year', 'Previous Year'),
         ('30_days', 'Last 30 Days'),
         ('three_months', 'Last 3 Months'),
         ('one_year', 'Last 12 Months'),
        ]
        , required=True, default='last_year', string='Based on', readonly=False)
    based_on_readonly = fields.Char(compute='_compute_suggestion_fields')
    percent_factor = fields.Integer(default=100, required=True)
    quantity = fields.Float(compute='_compute_suggestion_fields', digits='Product Unit')
    quantity_before_scale = fields.Float(compute='_compute_suggestion_fields', digits='Product Unit')

    def action_open_suggest_forecasted_form_view(self, mps_id):
        context = dict(self.env.context)
        context['default_mrp_mps_id'] = mps_id
        return {
            'type': 'ir.actions.act_window',
            'name': _("Suggest Forecasted Demand"),
            'target': 'new',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'res_id': False,
            'view_id': self.env.ref('mrp_mps.mrp_mps_forecast_suggestion_form_view').id,
            'res_model': 'mrp.mps.forecast.suggestion',
            'context': context,
        }

    @api.constrains('percent_factor')
    def _check_percent_factor_gte_0(self):
        if self.percent_factor < 0:
            raise ValidationError(_("Percent factor cannot be less than zero."))

    @api.depends('period', 'based_on', 'percent_factor')
    def _compute_suggestion_fields(self):
        period_index = 0
        period_scale = self.env.context.get('period_scale')
        based_on_date = ''
        qty_before_scale = 0
        rounding = self.mrp_mps_id.product_uom_id.rounding

        if self.period:
            period_index = self.period - 1
            date_range = self.mrp_mps_id.company_id._get_date_range(years=1, force_period=period_scale)
            start_chosen_date, end_chosen_date = date_range[period_index]

            match period_scale:
                case 'year':
                    based_on_date = _("%(year)s", year=start_chosen_date.year)
                case 'month':
                    based_on_date = _("%(month)s %(year)s",
                    month=start_chosen_date.strftime("%b"), year=start_chosen_date.year)
                case 'week':
                    based_on_date = _("Week %(week)s (%(start_day)s-%(end_day)s/%(month)s) %(year)s",
                    week=format_date(self.env, start_chosen_date, date_format='w'),
                    start_day=start_chosen_date.day,
                    end_day=end_chosen_date.day,
                    month=end_chosen_date.strftime("%b"),
                    year=end_chosen_date.year,
                    )
                case 'day':
                    based_on_date = _("%(month)s %(day)s %(year)s",
                    day=start_chosen_date.day,
                    month=start_chosen_date.strftime("%b"),
                    year=start_chosen_date.year,
                    )

        if self.period or self.based_on in ['30_days', 'three_months', 'one_year']:
            suggestion_quantities = self._get_suggestion_quantities(period_scale=period_scale)
            qty_before_scale = suggestion_quantities[period_index]

        self.quantity_before_scale = float_round(qty_before_scale, precision_rounding=rounding, rounding_method='UP')
        self.quantity = float_round(qty_before_scale * (self.percent_factor / 100), precision_rounding=rounding, rounding_method='UP')
        self.based_on_readonly = based_on_date

    def _get_suggestion_quantities(self, period_scale=False):
        if self.based_on in ['last_year', 'actual_demand'] or self.period:
            return self._get_suggestion_quantities_for_period_type(period_scale=period_scale)
        else:
            return self._get_suggestion_quantities_for_period_length(period_scale=period_scale)

    def _get_suggestion_quantities_for_period_type(self, period_scale=False):
        """
        Return a list of quantities, each is a suggestion demand for the matched period of the selected type.
        """
        suggestion_quantities = []
        years = 0 if self.based_on == 'actual_demand' else 1
        date_range = self.mrp_mps_id.company_id._get_date_range(years=years, force_period=period_scale)
        outgoing_qty, outgoing_qty_done, __, __ = self.mrp_mps_id._get_outgoing_qty(date_range)

        for date in date_range:
            period_qty = 0
            key = (date, self.product_id, self.mrp_mps_id.warehouse_id)
            period_qty += outgoing_qty_done.get(key, 0.0)

            if self.based_on == 'actual_demand':
                period_qty += outgoing_qty.get(key, 0.0)

            suggestion_quantities.append(period_qty)

        return suggestion_quantities

    def _get_suggestion_quantities_for_period_length(self, period_scale=False):
        """
        Return a list of quantities, each is a suggestion demand representing a ratio between
        the length of the period of the selected type and the length of the demand period.
        """
        if period_scale == 'year':
            multiplier_monthly_demand = 12
        elif period_scale == 'month':
            multiplier_monthly_demand = 1
        elif period_scale == 'week':
            multiplier_monthly_demand = 7 / (365.25 / 12)
        else:
            multiplier_monthly_demand = 1 / (365.25 / 12)

        context = {
            'suggest_based_on': self.based_on,
            'warehouse_id': self.mrp_mps_id.warehouse_id.id,
        }
        product = self.product_id.with_context(context)
        qty = product.monthly_demand * multiplier_monthly_demand
        return ([qty] * self.mrp_mps_id.company_id['manufacturing_period_to_display_%s' % period_scale])

    def apply_forecast_quantity_suggestion(self):
        self.ensure_one()
        period_scale = self.env.context.get('period_scale')
        rounding = self.mrp_mps_id.product_uom_id.rounding

        if self.period:
            period_index = self.period - 1
            self.mrp_mps_id.set_forecast_qty(period_index, self.quantity, period_scale=period_scale)
        else:
            suggestion_quantities = self._get_suggestion_quantities(period_scale=period_scale)

            for i in range(self.mrp_mps_id.company_id['manufacturing_period_to_display_%s' % period_scale]):
                quantity_to_suggest = suggestion_quantities[i]
                quantity_to_suggest = float_round(quantity_to_suggest * (self.percent_factor / 100), precision_rounding=rounding, rounding_method='UP')
                self.mrp_mps_id.set_forecast_qty(i, quantity_to_suggest, period_scale=period_scale)
