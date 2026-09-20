# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from datetime import timedelta

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

from .wise_request import Wise
from odoo.addons.l10n_us_direct_deposit.models.res_company import ICP_LOG_NAME

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    wise_api_key = fields.Char(
        related='company_id.wise_api_key',
        readonly=False,
        string='Wise API Key',
    )
    wise_environment = fields.Selection(
        related='company_id.wise_environment',
        readonly=False,
        string='Wise Environment',
    )

    wise_profile_identifier = fields.Char(
        related='company_id.wise_profile_identifier',
        readonly=True,
        string='Wise Profile ID',
    )

    def button_wise_enable_logging(self):
        self.env['ir.config_parameter'].sudo().set_param(
            ICP_LOG_NAME,
            (fields.Datetime.now() + timedelta(minutes=30)).strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        )
        return True

    def button_wise_open_logs(self):
        return {
            'name': self.env._("Wise Logging"),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.logging',
            'view_mode': 'list,form',
            'domain': [('name', '=', 'Wise API Logger')],
        }

    def action_connect_wise(self):
        """Connect to Wise API and retrieve profile information"""
        if not self.wise_api_key:
            raise UserError(self.env._("Please enter your Wise API Key first."))

        profile_type = 'business'
        wise_api = Wise(self.company_id)
        profiles = wise_api.get_profile(profile_type=profile_type)
        if wise_api.has_errors(profiles):
            raise UserError(self.env._("Failed to retrieve Wise profiles: %(wise_error)s", wise_error=wise_api.format_errors(profiles)))

        profile_data = next((p for p in profiles if p.get('type') == profile_type), profiles[0] if profiles else None)

        if profile_type == 'business':
            name = profile_data['details']['name']
        else:
            name = profile_data['details']['firstName'] + ' ' + profile_data['details']['lastName']

        self.company_id.wise_profile_identifier = profile_data.get('id')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': self.env._('Successfully connected to Wise profile: %(wise_profile_name)s', wise_profile_name=name),
                'type': 'success',
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
