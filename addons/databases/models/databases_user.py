from odoo import api, fields, models


class DatabasesUser(models.Model):
    _description = "Database User"
    _name = 'databases.user'

    project_id = fields.Many2one('project.project', string="Database", ondelete='cascade', index='btree',
                                 required=True, domain=[('database_hosting', '!=', False)])
    name = fields.Char(required=True)
    login = fields.Char(required=True)
    latest_authentication = fields.Datetime(readonly=True)
    local_user_id = fields.Many2one('res.users', compute='_compute_local_user_id')

    @api.depends('login')
    def _compute_local_user_id(self):
        local_users_by_login = dict(
            self.env['res.users']._read_group([('login', 'in', self.mapped('login'))], ['login'], ['id:recordset'])
        )
        for db_user in self:
            db_user.local_user_id = local_users_by_login.get(db_user.login, False)

    def action_invite_users(self):
        return self.project_id.action_database_invite_users()

    def action_remove_users(self):
        return self.project_id.action_database_remove_users(self.local_user_id.ids)
