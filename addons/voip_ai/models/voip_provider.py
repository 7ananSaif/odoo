from odoo import fields, models


class VoipProvider(models.Model):
    _inherit = "voip.provider"

    transcription_policy = fields.Selection(
        help="Transcribe the call into text with OpenAI.",
        selection=[
            ("disabled", "Disable"),
            ("always", "Force for all users"),
        ],
        default="disabled",
        required=True,
    )
