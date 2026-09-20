from datetime import date
from random import randint

from babel.dates import format_date
from dateutil.relativedelta import relativedelta
from werkzeug.exceptions import Forbidden

from odoo.http import Controller, request, route
from odoo.tools.misc import get_lang


class EsgDashboard(Controller):
    def _build_data_per_scope(self, start_date, end_date):
        # Quantity of carbon emissions per scope during end_date year
        data_per_scope = dict(request.env['esg.carbon.emission.report']._read_group(
            domain=[
                ('esg_emission_factor_id', '!=', False),
                ('date', '<=', end_date),
                ('date', '>=', start_date),
            ],
            groupby=['scope'],
            aggregates=['esg_emissions_value_t:sum'],
        ))
        scope_names = {
            'direct': request.env._('Scope 1'),
            'indirect': request.env._('Scope 2'),
            'indirect_others': request.env._('Scope 3'),
        }

        # If no data found from start of current year to now, build sample data
        if not data_per_scope:
            data_per_scope = {
                scope: randint(50, 100)
                for scope in scope_names.values()
            }
            is_sample = True
        else:
            data_per_scope = dict(sorted({
                scope_names.get(scope): round(value, 2)
                for scope, value in data_per_scope.items()
            }.items()))
            is_sample = False

        return {
            'data': data_per_scope,
            'is_sample': is_sample,
        }

    def _build_graph_config_per_scope(self, data, title, is_sample=False):
        return {
            'type': 'bar',
            'data': {
                'labels': list(data.keys()),
                'datasets': [
                    {
                        'label': self.env._("tCO₂e"),
                        'data': list(data.values()),
                        'backgroundColor': 'rgba(78, 167, 242, 1)' if not is_sample else 'rgba(235, 235, 235, 1)',
                    },
                ],
            },
            'options': {
                'scales': {
                    'y': {
                        'display': False,
                    },
                    'x': {
                        'ticks': {
                            'color': 'black',
                        },
                    },
                },
                'plugins': {
                    'legend': {
                        'display': False,
                    },
                    'title': {
                        'display': not is_sample,
                        'text': title,
                        'color': '#4F4F4F',
                        'font': {
                            'size': 18,
                        },
                    },
                    'tooltip': {
                        'enabled': not is_sample,
                        'intersect': False,
                        'position': 'nearest',
                        'caretSize': 0,
                    },
                },
                'aspectRatio': 4,
            },
        }

    def _get_carbon_analytics_section_data(self):
        has_unassigned_emissions = request.env['account.move.line'].search_count([
            ('esg_emission_factor_id', '=', False),
            ('quantity', '>', 0),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', 'in', request.env['account.account'].ESG_VALID_ACCOUNT_TYPES),
        ], limit=1)
        return {
            'has_unassigned_emissions':  has_unassigned_emissions,
        }

    def _build_data_per_month(self, start_date, end_date):
        # Cumulative distribution of carbon emissions per month, displayed from start_date to end_date
        data = dict(request.env['esg.carbon.emission.report']._read_group(
            domain=[
                ('esg_emission_factor_id', '!=', False),
                ('date', '<=', end_date),
                ('date', '>=', start_date),
            ],
            groupby=['date:month'],
            aggregates=['esg_emissions_value_t:sum'],
        ))

        # Generate a dictionary with all months from start_date to end_date
        start_date = start_date.replace(day=1)
        end_date = end_date.replace(day=1)
        current_date = start_date
        data_per_month = {}
        while current_date <= end_date:
            data_per_month[current_date] = 0.0
            next_month = current_date.month % 12 + 1
            next_year = current_date.year + (1 if next_month == 1 else 0)
            current_date = current_date.replace(month=next_month, year=next_year)

        if not data:  # If no data, build sample data
            for month in data_per_month:
                data_per_month[month] = randint(50, 100)
            is_sample = True

        else:
            is_sample = False
            accumulated_value = 0.0
            for month in data_per_month:
                if month in data:
                    data_per_month[month] = data[month] + accumulated_value
                    accumulated_value += data[month]
                else:
                    data_per_month[month] = accumulated_value

        locale = get_lang(request.env).code
        data_per_month = {format_date(month, 'LLLL Y', locale=locale): round(value, 2) for month, value in data_per_month.items()}

        return {
            'data': data_per_month,
            'is_sample': is_sample,
        }

    def _build_graph_config_per_month(self, data, is_sample=False):
        return {
            'type': 'line',
            'data': {
                'labels': list(data.keys()),
                'datasets': [
                    {
                        'label': self.env._("tCO₂e"),
                        'data': list(data.values()),
                        'backgroundColor': 'rgba(135, 90, 123, 0.2)' if not is_sample else 'rgba(135, 90, 123, 0.05)',
                        'fill': 'start',
                        'borderWidth': 2,
                        'borderColor': 'rgba(135, 90, 123, 1)' if not is_sample else 'rgba(135, 90, 123, 0.1)',
                    },
                ],
            },
            'options': {
                'scales': {
                    'x': {
                        'ticks': {
                            'display': False,
                        },
                        'grid': {
                            'display': False,
                        },
                    },
                    'y': {
                        'display': False,
                        'ticks': {
                            'display': False,
                        },
                        'grid': {
                            'display': False,
                        },
                        'beginAtZero': all(value == 0.0 for value in data.values()),
                    },
                },
                'plugins': {
                    'legend': {
                        'display': False,
                    },
                    'tooltip': {
                        'enabled': not is_sample,
                        'intersect': False,
                        'position': 'nearest',
                        'caretSize': 0,
                    },
                },
                'aspectRatio': 4,
            },
        }

    def _get_carbon_footprint_section_data(self, data, is_sample=False):
        section_data = {
            'last_months_percentage': self.env._("n/a"),
            'last_year_percentage': self.env._("n/a"),
        }
        if not is_sample:
            months = list(data.keys())
            current_month_value = data[months[-1]]
            last_months_value = data[months[-6]]
            last_year_value = data[months[-12]]

            if last_months_value:
                section_data['last_months_percentage'] = round(((current_month_value - last_months_value) / last_months_value) * 100, 2)
            if last_year_value:
                section_data['last_year_percentage'] = round(((current_month_value - last_year_value) / last_year_value) * 100, 2)
        return section_data

    def _get_dashboard_data(self):
        end_date = date.today()
        # Create data for bar chart grouped by scope
        start_date = end_date.replace(day=1, month=1)
        data_per_scope = self._build_data_per_scope(start_date, end_date)
        title = end_date.year
        graph_config_per_scope = self._build_graph_config_per_scope(data_per_scope['data'], title, data_per_scope['is_sample'])
        carbon_analytics_section_data = self._get_carbon_analytics_section_data()

        # Create data for line chart grouped by month-year
        start_date = end_date - relativedelta(years=1)
        data_per_month = self._build_data_per_month(start_date, end_date)
        graph_config_per_month = self._build_graph_config_per_month(data_per_month['data'], data_per_month['is_sample'])
        carbon_footprint_section_data = self._get_carbon_footprint_section_data(data_per_month['data'], data_per_month['is_sample'])

        return {
            'carbon_analytics_box': {
                'graph_config': graph_config_per_scope,
                'has_unassigned_emissions': carbon_analytics_section_data['has_unassigned_emissions'],
            },
            'carbon_footprint_box': {
                'graph_config': graph_config_per_month,
                'last_months_percentage': carbon_footprint_section_data['last_months_percentage'],
                'last_year_percentage': carbon_footprint_section_data['last_year_percentage'],
            },
        }

    @route('/esg/dashboard', type='jsonrpc', auth='user')
    def get_esg_dashboard(self, company_ids):
        if not request.env['esg.carbon.emission.report'].has_access('read'):
            raise Forbidden()
        request.update_context(allowed_company_ids=company_ids)
        return self._get_dashboard_data()
