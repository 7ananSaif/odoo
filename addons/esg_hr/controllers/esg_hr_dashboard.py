from odoo.http import request

from odoo.addons.esg.controllers.esg_dashboard import EsgDashboard


class EsgHrDashboard(EsgDashboard):

    def _get_sex_distribution_data(self):
        sex_selection = dict(request.env['esg.employee.report']._get_sex_selection())
        is_sample = False

        employee_count_per_sex = {
            sex_selection.get(sex): count
            for sex, count in request.env['hr.employee']._read_group(
                domain=[
                    ('company_id', 'in', request.env.companies.ids),
                    ('sex', '!=', False),
                ],
                groupby=['sex'],
                aggregates=['id:count'],
            )
        }
        if not employee_count_per_sex:
            employee_count_per_sex = dict.fromkeys(sex_selection.values(), 3)
            is_sample = True

        return {
            'data': employee_count_per_sex,
            'is_sample': is_sample,
        }

    def _build_graph_config(self, data, is_sample=False):
        # Pie chart showing sex distribution
        config = {
            'type': 'pie',
            'data': {
                'labels': list(data.keys()),
                'datasets': [
                    {
                        'label': self.env._('Count'),
                        'data': list(data.values()),
                    },
                ],
            },
            'options': {
                'aspectRatio': 4,
                'maintainAspectRatio': False,
                'plugins': {
                    'legend': {
                        'display': False,
                    },
                },
            },
        }
        if is_sample:
            config['data']['datasets'][0]['backgroundColor'] = 'rgba(235, 235, 235, 1)'
        return config

    def _get_dashboard_data(self):
        data = super()._get_dashboard_data()
        if not self.env.user.has_group('hr.group_hr_user'):
            return data
        sex_distribution_data = self._get_sex_distribution_data()
        graph_config = self._build_graph_config(sex_distribution_data['data'], sex_distribution_data['is_sample'])
        return {
            **data,
            'sex_parity_box': {
                'graph_config': graph_config,
                'overall_pay_gap': request.env['esg.employee.report'].get_overall_pay_gap(),
            },
        }
