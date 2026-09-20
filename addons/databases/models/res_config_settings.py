from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    databases_apiuser = fields.Char(
        string="Odoo.com API User",
        config_parameter="databases.odoocom_apiuser",
        groups='base.group_system',
    )
    databases_apikey = fields.Char(
        string="Odoo.com API Key",
        config_parameter="databases.odoocom_apikey",
        groups='base.group_system',
    )
    databases_project_template_id = fields.Many2one(
        'project.project',
        domain=[('is_template', '=', True)],
        string="Project template",
        config_parameter="databases.odoocom_project_template",
        groups='base.group_system',
    )
