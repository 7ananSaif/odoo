from odoo import fields, models


class PlanningRole(models.Model):
    _inherit = 'planning.role'

    product_ids = fields.One2many(
        domain="""[
            ('type', '=', 'service'),
            ('sale_ok', '=', True),
            '|', ('planning_role_id', '=', False), ('planning_role_id', '=', id),
            ('service_tracking', 'in', ['no', 'task_global_project', 'task_in_project', 'project_only'])
        ]""",
    )
