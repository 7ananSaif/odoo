from odoo import api, fields, models


class ProjectTemplateCreateWizard(models.TransientModel):
    _inherit = 'project.template.create.wizard'

    database_hosting = fields.Selection(
        selection=[
            ('saas', 'Odoo Online'),
            ('paas', 'Odoo.sh'),
            ('premise', 'On Premise'),
            ('other', 'Outside of Odoo'),
        ],
        string='Hosting',
    )
    database_name = fields.Char(string="Database Name")
    database_url = fields.Char(string="Database URL")
    database_api_login = fields.Char(string="Database API Login")
    database_api_key = fields.Char(string="Database API Key")
    database_fetch_documents = fields.Boolean("Fetch Documents", default=True)
    database_fetch_draft_entries = fields.Boolean("Fetch Draft Journal Entries", default=True)
    database_fetch_tax_returns = fields.Boolean("Fetch Tax Returns", default=True)

    def _get_template_whitelist_fields(self):
        whitelist = super()._get_template_whitelist_fields()
        if self.env.context.get('databases_template'):
            whitelist.extend([
                'database_hosting',
                'database_name',
                'database_url',
                'database_api_login',
                'database_api_key',
                'database_fetch_documents',
                'database_fetch_draft_entries',
                'database_fetch_tax_returns',
            ])
        return whitelist

    @api.model
    def action_open_template_view(self):
        action = super().action_open_template_view()

        if self.env.context.get('databases_template'):
            view = self.env.ref('databases.project_project_view_form_simplified_template', raise_if_not_found=False)
            if view:
                action['views'] = [(view.id, 'form')]

        return action
