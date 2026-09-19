# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from datetime import datetime

from odoo import SUPERUSER_ID, api, fields, models
from odoo.modules.registry import Registry
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)
ICP_LOG_NAME = 'l10n_us_direct_deposit.log.end.date'


class ResCompany(models.Model):
    _inherit = 'res.company'

    wise_api_key = fields.Char(
        string='Wise API Key',
        help='API key obtained from Wise platform',
        groups='base.group_system',
    )
    wise_environment = fields.Selection([
        ('sandbox', 'Sandbox'),
        ('production', 'Production'),
    ], string='Wise Environment', default='sandbox', groups='base.group_system')

    wise_profile_identifier = fields.Char(
        string='Wise Profile ID',
        help='Profile ID retrieved from Wise API',
        compute='_compute_wise_profile',
        store=True,
        groups='base.group_system',
    )
    wise_connected = fields.Boolean(
        string='Wise Connected',
        compute='_compute_wise_connected',
        compute_sudo=True,
    )

    @api.depends('wise_api_key', 'wise_environment')
    def _compute_wise_profile(self):
        for company in self:
            company.wise_profile_identifier = False

    @api.depends('wise_profile_identifier', 'wise_api_key')
    def _compute_wise_connected(self):
        for company in self:
            company.wise_connected = bool(company.wise_profile_identifier and company.wise_api_key)

    def _log_external_wise_request(self, message, func):
        """ Log when the ICP's value is in the future. """
        log_end_date = self.env['ir.config_parameter'].sudo().get_param(ICP_LOG_NAME, '')
        try:
            log_end_date = datetime.strptime(log_end_date, DEFAULT_SERVER_DATETIME_FORMAT)
            need_log = fields.Datetime.now() < log_end_date
        except ValueError:
            need_log = False
        if need_log:
            # This creates a new cursor to make sure the log is committed even when an
            # exception is thrown later in this request.
            self.env.flush_all()
            dbname = self.env.cr.dbname
            with Registry(dbname).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env['ir.logging'].create({
                    'name': "Wise API Logger",
                    'type': 'server',
                    'level': 'DEBUG',
                    'dbname': dbname,
                    'message': message,
                    'path': 'l10n_us_direct_deposit',
                    'func': func,
                    'line': 1,
                })
