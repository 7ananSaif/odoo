from odoo import api, fields, models


class ResUsersSettings(models.Model):
    _inherit = "res.users.settings"

    def _get_default_voip_provider(self):
        return self.env["voip.provider"].sudo().search([("company_id", "in", [self.env.company.id, False])], limit=1).sudo(False)

    voip_provider_id = fields.Many2one(
        "voip.provider", string="VoIP Provider",
        default=_get_default_voip_provider,
    )

    # Credentials for authentication to the PBX server
    voip_username = fields.Char(
        "VoIP username / Extension number",
        help="The username (typically the extension number) that will be used to register with the PBX server.",
    )
    voip_secret = fields.Char("VoIP secret", help="The password that will be used to register with the PBX server.")

    should_call_from_another_device = fields.Boolean(
        "Call from another device",
        help="""Specify a phone number so that placing a call in Odoo Phone will ring your preferred device (your desk phone or cell phone) and then connect you to the recipient.""",
    )
    external_device_number = fields.Char(
        "External device number",
        help="""Specify a phone number so that placing a call in Odoo Phone will ring your preferred device (your desk phone or cell phone) and then connect you to the recipient.""",
    )

    # Mobile stuff
    how_to_call_on_mobile = fields.Selection(
        [("ask", "Always Ask"), ("voip", "Odoo Phone"), ("phone", "Phone's Default App")],
        default="ask",
        string="Default phone app",
        help="""Choose which app to open when clicking on a phone number in the Odoo Mobile app.""",
        required=True,
    )

    do_not_disturb_until_dt = fields.Datetime(
        string="Do Not Disturb until",
        help="If set, Odoo Phone will be in Do Not Disturb mode until this time."
    )

    @api.model
    def _format_settings(self, fields_to_format):
        res = super()._format_settings(fields_to_format)
        if "do_not_disturb_until_dt" in fields_to_format:
            res["do_not_disturb_until_dt"] = fields.Datetime.to_string(self.do_not_disturb_until_dt)
        return res
