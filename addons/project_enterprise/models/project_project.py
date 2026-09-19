from datetime import datetime, time, timedelta

from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def web_gantt_write(self, data):
        # If it's schedule context (One of the projects doesn't have date)
        # we need to remove m2o field like user_id from data if they are empty to keep the old values
        if not self[0].date:
            for field in [
                f_name for f_name, value in data.items()
                if (
                    not value
                    and f_name in self._fields
                    and self._fields[f_name].type == 'many2one'
                )
            ]:
                del data[field]

        return self.write(data)

    def action_view_tasks(self):
        action = super().action_view_tasks()
        if not self.allow_milestones:
            action['views'] = [
                (view_id if view_type != 'map' else self.env.ref('project_enterprise.project_task_map_view_no_title_no_milestone').id, view_type)
                for view_id, view_type in action['views']
            ]
        if self._get_hide_partner() or self.is_template:
            action['views'] = [(view_id, view_type) for view_id, view_type in action['views'] if view_type != 'map']
        return action

    def action_create_from_template(self, values=None, role_to_users_mapping=None):
        project = super().action_create_from_template(values=values, role_to_users_mapping=role_to_users_mapping)
        if project.date_start and self.date_start:
            delta = project.date_start - self.date_start
            first_possible_date_per_task = {}
            tasks_to_schedule = self.env['project.task']
            project_start_datetime = datetime.combine(project.date_start, time.min)
            project_end_datetime = datetime.combine(project.date + timedelta(days=1), time.min)

            for original_task, copied_task in zip(self.task_ids, project.task_ids):
                if original_task.planned_date_begin:
                    first_possible_date_per_task[copied_task.id] = original_task.planned_date_begin + delta
                    tasks_to_schedule += copied_task
            tasks_to_schedule._scheduling({
                "planned_date_begin": datetime.strftime(project_start_datetime, '%Y-%m-%d %H:%M:%S'),
                "date_deadline": datetime.strftime(project_end_datetime, '%Y-%m-%d %H:%M:%S'),
            }, project_end_datetime, first_possible_date_per_task=first_possible_date_per_task)
        else:
            tasks_to_schedule = self.env['project.task']
            project_start_datetime = datetime.combine(project.date_start or fields.Date.today(), time.min)
            project_end_datetime = project_start_datetime + timedelta(days=365)
            for original_task, copied_task in zip(self.task_ids, project.task_ids):
                if original_task.planned_date_begin:
                    tasks_to_schedule += copied_task
            tasks_to_schedule._scheduling({
                "planned_date_begin": datetime.strftime(project_start_datetime, '%Y-%m-%d %H:%M:%S'),
                "date_deadline": datetime.strftime(project_end_datetime, '%Y-%m-%d %H:%M:%S'),
            }, project_end_datetime)
        return project
