# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import api, models, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.model
    def get_empty_list_help(self, help_message):
        default_alias = self.env.ref("project_enterprise_hr.mail_alias_todo", raise_if_not_found=False)
        if default_alias and self.env.company.alias_domain_id and self.env.context.get('show_todo_mail_helper', False):
            bounce_mail = default_alias.alias_name + "@" + self.env.company.alias_domain_id.name
            help_message += Markup("<p>%s</p>") % (
                _(
                    "Create new to-dos by sending an email to %s",
                    Markup("<a href='mailto:{0}'>{0}</a>").format(bounce_mail),
                )
            )
        return super().get_empty_list_help(help_message)

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        if custom_values is None:
            custom_values = {}
        if not custom_values.get('project_id', True) and msg_dict.get('email_from'):
            user_ids, _dummy, _dummy = self._find_internal_users_from_address_mail(msg_dict.get('email_from'))
            if user_ids:
                custom_values['user_ids'] = user_ids

        return super().message_new(msg_dict, custom_values)
