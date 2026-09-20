from odoo import api, fields, models

from ..api import ApiError, OdooDatabaseApi


class DatabasesInviteUsersWizard(models.TransientModel):
    _name = 'databases.manage_users.wizard'
    _description = 'Database Users Invitation Wizard'

    database_ids = fields.Many2many(
        comodel_name='project.project',
        domain=[('database_hosting', 'not in', (False, 'other'))],
        default=lambda self: self.env.context.get('active_ids')
    )
    mode = fields.Selection([
        ('invite', 'Invitation'),
        ('remove', 'Removal'),
    ], required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], required=True, default='draft')
    error_message = fields.Char(default='')
    user_ids = fields.Many2many('res.users', domain=[('share', '=', False)])
    summary_message = fields.Char(compute='_compute_summary_message')
    everywhere_user_ids = fields.Many2many('res.users', compute='_compute_everywhere_user_ids')
    removable_user_ids = fields.Many2many('res.users', compute='_compute_removable_user_ids')

    @api.depends('database_ids')
    def _compute_summary_message(self):
        for record in self:
            if record.state == 'draft':
                if record.mode == 'invite':
                    if len(record.database_ids) == 1:
                        record.summary_message = self.env._(
                            "Select the users you want to invite to the database %(database_name)s.",
                            database_name=record.database_ids.name
                        )
                    else:
                        record.summary_message = self.env._(
                            "Select the users you want to invite to the %(nb_databases)s selected databases.",
                            nb_databases=len(record.database_ids)
                        )
                else:
                    if len(record.database_ids) == 1:
                        record.summary_message = self.env._(
                            "Select the users you want to remove from the database %(database_name)s.",
                            database_name=record.database_ids.name
                        )
                    else:
                        record.summary_message = self.env._(
                            "Select the users you want to remove from the %(nb_databases)s selected databases.",
                            nb_databases=len(record.database_ids)
                        )
            elif record.state == 'done':
                if record.error_message:
                    record.summary_message = self.env._("An error occurred: %s", record.error_message)
                elif record.mode == 'invite':
                    record.summary_message = self.env._(
                        "These users were successfully invited to %(nb_databases)s databases.",
                        nb_databases=len(record.database_ids)
                    )
                else:
                    record.summary_message = self.env._(
                        "These users were successfully removed from %(nb_databases)s databases.",
                        nb_databases=len(record.database_ids)
                    )

    @api.depends('database_ids.database_user_ids.local_user_id')
    def _compute_everywhere_user_ids(self):
        for rec in self:
            if not rec.database_ids:
                rec.everywhere_user_ids = None
                continue
            # Compute the intersection of local_user_ids in each database
            dbit = iter(rec.database_ids)
            everywhere_user_ids = next(dbit).database_user_ids.local_user_id
            for db in dbit:
                everywhere_user_ids &= db.database_user_ids.local_user_id
            rec.everywhere_user_ids = everywhere_user_ids

    @api.depends('database_ids.database_user_ids.local_user_id')
    def _compute_removable_user_ids(self):
        for rec in self:
            rec.removable_user_ids = rec.database_ids.database_user_ids.local_user_id

    def _open(self):
        if self.mode == 'invite':
            name = self.env._("Invitation is done")
        elif self.mode == 'remove':
            name = self.env._("User removal is done")

        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'views': [[False, 'form']],
        }

    def action_invite_users(self):
        existing_users = {
            (du.login, du.project_id.id)
            for du in self.env['databases.user'].search([
                ('login', 'in', self.user_ids.mapped('login')),
                ('project_id', 'in', self.database_ids.ids),
            ])
        }
        new_users = self.env['databases.user'].create([
            {
                'project_id': db.id,
                'login': user.login,
                'name': user.name,
            }
            for db in self.database_ids
            for user in self.user_ids
            if (user.login, db.id) not in existing_users
        ])

        for db, db_users in new_users.grouped('project_id').items():
            args = [db.database_url, db.database_name, db.database_api_login, db.sudo().database_api_key_to_use]
            if not all(args):
                self.error_message += self.env._(
                    "Error while connecting to %(url)s: We are missing the database name, the api login or the api key\n",
                    url=db.database_url,
                )
                db_users.unlink()
                continue
            db_api = OdooDatabaseApi(*args)

            try:
                db_api.invite_users(db_users.mapped('login'))
            except ApiError as e:
                self.error_message += self.env._(
                    "Error while creating users on %(dbname)s: %(message)s\n",
                    dbname=db.database_name,
                    message=e.args[0],
                )
                db_users.unlink()
                continue

        self.state = 'done'
        return self._open()

    def action_remove_users(self):
        users_to_delete = self.env['databases.user'].search([
            ('login', 'in', self.user_ids.mapped('login')),
            ('project_id', 'in', self.database_ids.ids),
        ])

        for db, db_users in users_to_delete.grouped('project_id').items():
            args = [db.database_url, db.database_name, db.database_api_login, db.sudo().database_api_key_to_use]
            if not all(args):
                self.error_message += self.env._(
                    "Error while connecting to %(url)s: We are missing the database name, the api login or the api key\n",
                    url=db.database_url,
                )
                users_to_delete -= db_users
                continue
            db_api = OdooDatabaseApi(*args)

            try:
                db_api.remove_users(db_users.mapped('login'))
            except ApiError as e:
                self.error_message += self.env._(
                    "Error while removing users from %(dbname)s: %(message)s\n",
                    dbname=db.database_name,
                    message=e.args[0],
                )
                users_to_delete -= db_users
                continue

        users_to_delete.unlink()

        self.state = 'done'
        return self._open()
