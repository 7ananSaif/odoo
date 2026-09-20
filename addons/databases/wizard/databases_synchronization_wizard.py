import re
from odoo import api, fields, models
from odoo.fields import Domain

from ..api import ApiError, OdooComApi, OdooDatabaseApi, _humanize_version


class DatabasesSynchronizationWizard(models.TransientModel):
    _name = 'databases.synchronization.wizard'
    _description = 'Database Synchronization Wizard'

    error_message = fields.Char(default='')
    summary_message = fields.Char(compute='_compute_summary_message')
    database_ids = fields.Many2many(
        comodel_name='project.project',
        domain=[('database_hosting', 'not in', (False, 'other'))],
    )
    created_database_ids = fields.Many2many(
        comodel_name='project.project',
        relation='databases_synchronization_wizard_created_databases_rel',
        domain=[('database_hosting', 'not in', (False, 'other'))],
    )
    property_definition = fields.Json()
    fetched_values = fields.Json()
    new_properties = fields.Json(string="New KPIs to add:")
    notify_user = fields.Boolean(default=False, required=True,
                                 help="Whether the user should be notified once the cron has finished synchronizing the databases")

    @api.depends('database_ids', 'created_database_ids')
    def _compute_summary_message(self):
        for record in self:
            record.summary_message = self.env._(
                "%(nb_new_dbs)s new databases, %(nb_updated_dbs)s updated.",
                nb_new_dbs=len(record.created_database_ids),
                nb_updated_dbs=len(record.database_ids)
            )

    def _open(self):
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Synchronization done successfully!"),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'views': [[False, 'form']],
        }

    def _can_update_from_odoo_com(self):
        ICP = self.env['ir.config_parameter'].sudo()
        apiuser = ICP.get_param('databases.odoocom_apiuser')
        apikey = ICP.get_param('databases.odoocom_apikey')
        return self.env.user.has_group('databases.group_databases_manager') and apiuser and apikey

    def _do_update_from_odoocom(self):
        """
            - Get db info from odoo.com
            - Create missing dbs
            - Switch unconfigured on premise/paas to saas
            - Update saas dbs
            - Report configured on premise/paas dbs detected in saas as not updated
        """
        self.check_access("write")

        # Get db info from Odoo
        ICP = self.env['ir.config_parameter'].sudo()
        apihost = ICP.get_param('databases.odoocom_apihost', 'https://www.odoo.com')
        apidb = ICP.get_param('databases.odoocom_apidb', 'openerp')
        apiuser = ICP.get_param('databases.odoocom_apiuser')
        apikey = ICP.get_param('databases.odoocom_apikey')

        if not (apiuser and apikey):
            return

        odoocom_api = OdooComApi(apihost, apidb, apiuser, apikey)
        try:
            databases = [db for db in odoocom_api.list_databases() if db['name'] != self.env.cr.dbname]
        except ApiError as e:
            self.error_message += self.env._(
                "Error while listing databases from %(dbname)s: %(message)s\n",
                dbname=apihost,
                message=e.args[0],
            )
            return

        # Create missing db
        Project = self.env['project.project']
        databases_by_url = {db['url']: db for db in databases}  # TODO: handle duplicate urls correctly
        existing_databases = Project.with_context(active_test=False).search([
            ('database_hosting', '!=', False),
            ('database_url', 'in', list(databases_by_url)),
        ])
        existing_urls = set(existing_databases.mapped('database_url'))
        template = Project._database_get_project_template()
        for db in databases:
            if db['url'] not in existing_urls:
                values = {
                    'name': db['name'],
                    'database_name': db['name'],
                    'database_hosting': 'saas',
                    'database_url': db['url'],
                    'database_api_login': db['login'],
                }
                if template:
                    self.created_database_ids |= template.action_create_from_template(values)
                else:
                    self.created_database_ids |= Project.create(values)

        # Update saas dbs
        saas_domain = [
            ('database_hosting', '=', 'saas'),
            ('database_url', 'in', list(databases_by_url)),
        ]
        # Switch unconfigured hosted db to saas
        hosting_should_be_saas = [
            ('database_hosting', 'in', ('paas', 'premise', 'other')),
            ('database_url', 'in', list(databases_by_url)),
            ('database_api_login', '=', False),
            ('database_api_key', '=', False),
        ]
        dbs_to_update = Project.with_context(active_test=False).search(Domain.OR([
            saas_domain,
            hosting_should_be_saas,
        ]))
        for db in dbs_to_update.try_lock_for_update():  # don't wait for db already updating
            db_info = databases_by_url[db.database_url]
            vals = {
                'database_hosting': 'saas',
                'database_name': db_info['name'],
                'database_api_login': db_info['login'],
            }
            if version := _humanize_version(db_info['version']):
                vals['database_version'] = version
            db.write(vals)

        self.database_ids |= self.created_database_ids

        dbs_ignored = existing_databases - dbs_to_update
        for db in dbs_ignored:
            self.error_message += self.env._(
                "The database %(url)s is registered as a saas database in odoo.com. As it seems to be configured we have left it as is.\n",
                url=db.database_url,
            )

    def _do_synchronize(self):
        self.check_access("write")

        if not self.database_ids:
            return self._open()

        try:
            immediate_sync_limit = int(self.env['ir.config_parameter'].sudo().get_param('databases.immediate_sync_limit', 20))
        except ValueError:
            immediate_sync_limit = 20

        if immediate_sync_limit and len(self.database_ids) > immediate_sync_limit:
            self.database_ids.sudo().database_last_synchro = False
            self.notify_user = True
            self.env.ref('databases.ir_cron_synchronize_databases')._trigger()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': self.env._("Synchronization of %d databases", len(self.database_ids)),
                    'message': self.env._("Database synchronization is running in the background. "
                                          "You will be notified upon completion."),
                    'type': 'info',
                    'sticky': False,
                },
            }

        # property.base.definition objects are readable only by role Settings
        database_kpi_base_definition_id = self.database_ids.sudo().database_kpi_base_definition_id
        database_kpi_base_definition_id.ensure_one()
        self.property_definition = database_kpi_base_definition_id.properties_definition

        for db in self.database_ids:
            db.database_last_synchro = fields.Datetime.now()
            if version := OdooDatabaseApi.fetch_version(db.database_url):
                db.database_version = version
            args = [db.database_url, db.database_name, db.database_api_login, db.sudo().database_api_key_to_use]
            if not all(args):
                self.error_message += self.env._(
                    "Error while connecting to %(url)s: We are missing the database name, the api login or the api key\n",
                    url=db.database_url,
                )
                continue
            db_api = OdooDatabaseApi(*args)
            self._read_users(db, db_api)
            self._read_kpis(db, db_api)

            db.database_nb_synchro_errors = 0

        return self._open()

    def _read_users(self, db, db_api):
        try:
            users = db_api.list_internal_users()
        except ApiError as e:
            self.error_message += self.env._(
                "Error while getting users from %(dbname)s: %(message)s\n",
                dbname=db.database_name,
                message=e.args[0],
            )
            return

        users = {u['login']: u for u in users}
        existing_users = db.database_user_ids
        common_users = existing_users.filtered(lambda u: u.login in users)
        missing_logins = set(users) - set(existing_users.mapped('login'))
        users_to_delete = existing_users - common_users

        users_to_delete.unlink()
        existing_users.sudo().create([
            {
                'project_id': db.id,
                'login': user['login'],
                'name': user['name'],
                'latest_authentication': user['login_date']
            }
            for user in users.values() if user['login'] in missing_logins
        ])
        for user in common_users:
            user_data = users[user.login]
            user.sudo().write({
                'name': user_data['name'],
                'latest_authentication': user_data['login_date'],
            })

    def _read_kpis(self, db, db_api):
        try:
            kpi_summary = db_api.get_kpi_summary()
        except ApiError as e:
            self.error_message += self.env._(
                "Error while getting KPIs from %(dbname)s: %(message)s\n",
                dbname=db.database_name,
                message=e.args[0],
            )
            return

        property_definition = {x['name']: x for x in self.property_definition or []}
        kpi_properties = {}
        for kpi in kpi_summary:
            if kpi['id'] == 'documents.inbox':
                if db.database_fetch_documents:
                    db.database_nb_documents = kpi['value']
                continue

            if kpi['id'].startswith('account_move_type.') and not db.database_fetch_draft_entries:
                continue

            if kpi['id'].startswith('account_return.') and not db.database_fetch_tax_returns:
                continue

            # property names must match odoo.orm.utils.regex_alphanumeric
            kpi_id = re.sub(r'[^a-z0-9]', '_', kpi['id'].lower())
            if kpi_id not in property_definition:
                property_definition[kpi_id] = {
                    'name': kpi_id,
                    'string': kpi['name'],
                }
                if kpi['type'] == 'integer':
                    property_definition[kpi_id].update({
                        'type': 'integer',
                        'default': 0,
                    })
                if kpi['type'] == 'return_status':
                    property_definition[kpi_id].update({
                        'type': 'selection',
                        'default': False,
                        'selection': [
                            ['late', '🔴'],
                            ['longterm', '⚪'],
                            ['to_do', '🟡'],
                            ['to_submit', '🟢⚪'],
                            ['done', '🟢'],
                        ],
                    })

            kpi_properties[kpi_id] = kpi['value']

        # property.base.definition objects are readable only by role Settings
        database_kpi_base_definition_id = self.database_ids.sudo().database_kpi_base_definition_id
        database_kpi_base_definition_id.ensure_one()
        previous_kpi_ids = {x['name'] for x in database_kpi_base_definition_id.properties_definition}
        self.write({
            'new_properties': {kpi_id: {'label': kpi['string'], 'checked': False}
                               for kpi_id, kpi in property_definition.items() if kpi_id not in previous_kpi_ids},
            'property_definition': list(property_definition.values()),
        })

        self.fetched_values = {
            **(self.fetched_values or {}),
            db.id: kpi_properties,
        }

    def action_add_metrics_to_dashboard(self):
        if not self.database_ids:
            return

        # property.base.definition objects are readable only by role Settings
        database_kpi_base_definition_id = self.database_ids.sudo().database_kpi_base_definition_id
        database_kpi_base_definition_id.ensure_one()
        existing_keys = {x['name'] for x in database_kpi_base_definition_id.properties_definition}
        properties_definition = [x for x in self.property_definition or []
                                 if x['name'] in existing_keys or self.new_properties[x['name']]['checked']]

        # sort the properties definition on the prefix of the name first, then on the string
        prefix_order = ('account_journal_type', 'account_move_type', 'account_return')
        sortable_properties_definition = [
            # index of the first matching prefix, defaulting to the end
            (next((i for i, prefix in enumerate(prefix_order) if x['name'].startswith(prefix)), len(prefix_order)),
            # then the displayed name
             x['string'], x)
            for x in properties_definition]
        properties_definition = [x[2] for x in sorted(sortable_properties_definition)]

        database_kpi_base_definition_id.write({
            'properties_definition': properties_definition,
        })

        for db in self.database_ids:
            if fetched_values := (self.fetched_values or {}).get(str(db.id)):  # JSON keys are strings
                db.sudo().write({
                    'database_kpi_properties': fetched_values,
                })

        action = {
            "type": "ir.actions.client",
            "tag": "soft_reload",
        }
        return action
