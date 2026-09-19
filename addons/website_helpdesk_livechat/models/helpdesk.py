# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.fields import Command


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    use_website_helpdesk_livechat = fields.Boolean(inverse='_inverse_use_website_helpdesk_livechat')

    def _inverse_use_website_helpdesk_livechat(self):
        self._create_livechat_channel()

    # ------------------------------------------------------------
        #  Hooks
    # ------------------------------------------------------------
    def _create_livechat_channel(self):
        LiveChat = self.env['im_livechat.channel']
        channel_vals_per_team_name = {}
        for team in self:
            if not (team.name and team.use_website_helpdesk_livechat):
                continue
            if team.name not in channel_vals_per_team_name:
                vals = {'name': team.name}
                if team.member_ids and team.auto_assignment:
                    vals['user_ids'] = [Command.set(team.member_ids.ids)]
                channel_vals_per_team_name[team.name] = vals
        if channel_vals_per_team_name:
            channel_names = {
                res['name']
                for res in LiveChat.search_read([('name', 'in', list(channel_vals_per_team_name.keys()))], ['name'])
            }
            vals_list = [vals for team_name, vals in channel_vals_per_team_name.items() if team_name not in channel_names]
            if vals_list:
                LiveChat.create(vals_list)

    # ------------------------------------------------------------
        # action methods
    # ------------------------------------------------------------
    def action_view_channel(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('im_livechat.im_livechat_channel_action')
        channel_ids = list(self.env['im_livechat.channel']._search([('name', '=', self.name)], limit=1))
        if channel_ids:
            action.update(res_id=channel_ids[0], views=[(False, 'form')])
        return action
