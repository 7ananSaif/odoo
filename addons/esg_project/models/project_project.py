from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.tools.convert import convert_file


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def _view_esg_project_tasks(self):
        project = self.env.ref('esg_project.esg_project_project_0')
        action = project.action_view_tasks()
        domain = action['domain']
        if domain:
            domain = domain.replace('active_id', str(project.id))
        else:
            domain = [('project_id', '=', project.id)]
        action['domain'] = domain
        initiative_action = self.env.ref("esg_project.esg_initiatives_server_action", raise_if_not_found=False)
        if path := (initiative_action.path if initiative_action else None):
            action["path"] = path
        action['help'] = self.env._("""
            <p class="o_view_nocontent_smiling_face">No tasks found. Let's create one!</p>
            <p>Keep track of the progress of your initiatives to take action on your impact from creation to completion.<br/>Collaborate efficiently by chatting in real-time or via email.</p>
        """)
        if not self._has_demo_data():
            action['help'] += self.env._("""
                <a class="btn btn-secondary mt-3" type="action" name="%d">Load sample data</a>
            """, self.env.ref('esg_project.action_load_demo_data').id)
        return action

    @api.ondelete(at_uninstall=False)
    def _prevent_esg_project_deletion(self):
        if self.env.ref('esg_project.esg_project_project_0') in self:
            raise ValidationError(self.env._('You cannot delete the ESG Project.'))

    @api.model
    def _has_demo_data(self):
        if not self.env.user.has_group('esg.esg_group_manager'):
            return True
        # This record only exists if the esg project demo data has been already loaded
        tag = self.env.ref('esg_project.esg_project_tags_0', raise_if_not_found=False)
        return bool(tag) or bool(self.env['ir.module.module'].search_count([('demo', '=', True)]))

    def _load_demo_data(self):
        if self._has_demo_data():
            return
        convert_file(self.sudo().env, 'esg_project', 'demo/demo_data.xml', None, mode='init')
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
