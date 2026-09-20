from odoo import _, fields, models
from odoo.exceptions import UserError


class IrActionsServer(models.Model):
    _inherit = 'ir.actions.server'

    # The documents actions add a check that the current document is in a folder
    # on which the current action is pinned (to avoid executing server action
    # means to be used in a different folder).
    usage = fields.Selection(
        selection_add=[('documents_embedded', 'Documents')],
        ondelete={'documents_embedded': 'set ir_actions_server'},
    )

    def action_open_documents_server_action_view(self):
        self.check_access('read')
        form_view = self.env.ref('documents.ir_actions_server_view_form_documents', raise_if_not_found=False)
        search_view = self.env.ref('documents.ir_actions_server_action_search_documents', raise_if_not_found=False)
        return {
            'context': {
                'default_model_id': self.env['ir.model']._get_id('documents.document'),
                'default_update_path': 'tag_ids',
                'default_usage': 'documents_embedded',
            },
            'display_name': _('Server Actions'),
            'domain': [
                ('model_name', '=', 'documents.document'),
                ('parent_id', '=', False),
            ],
            'help': """
                <div style="width:650px;">
                    <p class="d-none">%s</p>
                    <img class="w-100 w-md-75" src="/documents/static/img/documents_server_action.svg"/>
                </div>
            """ % _('No server actions found for Documents!'),
            'res_model': 'ir.actions.server',
            'target': 'current',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (form_view.id if form_view else False, 'form')],
            'search_view_id': [search_view.id if search_view else False, 'search'],
        }

    def _can_execute_action_on_records(self, records):
        if self.usage == 'documents_embedded':
            # Check that the action is in the pinned on the record's folder
            for record in records:
                record_actions = record.available_embedded_actions_ids.action_id
                record_server_actions_sudo = record_actions.sudo().filtered(lambda a: a.type == 'ir.actions.server')
                available_server_actions_sudo = self.env['ir.actions.server'].browse(record_server_actions_sudo.ids).sudo()

                # Add the child actions
                actions = available_server_actions_sudo
                while actions.child_ids:
                    next_actions = actions.child_ids - available_server_actions_sudo
                    available_server_actions_sudo |= actions.child_ids
                    actions = next_actions

                if self not in available_server_actions_sudo:
                    raise UserError(_('This action was not made available on the containing folder.'))

        return super()._can_execute_action_on_records(records)
