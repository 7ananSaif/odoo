from odoo.http import request

from odoo.addons.esg.controllers.esg_dashboard import EsgDashboard


class EsgProjectDashboard(EsgDashboard):

    def _get_initiatives_section_data(self):
        esg_project = request.env.ref('esg_project.esg_project_project_0')
        esg_stages = request.env['project.task.type'].search(
            domain=[('project_ids', 'in', esg_project.ids)],
            order='sequence',
            limit=3,
        )
        tasks_per_stage_label = dict.fromkeys(esg_stages.mapped('name'), 0)

        for stage, count in request.env['project.task']._read_group(
            domain=[
                ('stage_id', 'in', esg_stages.ids),
                ('is_closed', '=', False),
            ],
            groupby=['stage_id'],
            aggregates=['id:count'],
        ):
            tasks_per_stage_label[stage.name] = count
        tasks_per_stage_label = [{'name': name, 'count': count} for name, count in tasks_per_stage_label.items()]
        tasks_total_count = request.env['project.task'].search_count([
            ('project_id', '=', esg_project.id),
            ('is_closed', '=', False),
        ])

        return {
            'project_id': esg_project.id,
            'tasks_per_stage_label': tasks_per_stage_label,
            'tasks_total_count': tasks_total_count,
        }

    def _get_dashboard_data(self):
        data = super()._get_dashboard_data()
        if not self.env.user.has_group('project.group_project_user'):
            return data
        data['initiatives_box'] = self._get_initiatives_section_data()
        return data
