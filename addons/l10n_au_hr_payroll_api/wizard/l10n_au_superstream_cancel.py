# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class L10n_AuSuperStreamCancel(models.TransientModel):
    _name = "l10n_au.superstream.cancel"
    _description = "Cancel SuperStream"

    l10n_au_super_stream_id = fields.Many2one(
        comodel_name="l10n_au.super.stream",
        string="SuperStream",
        required=True,
    )
    l10n_au_cancel_type = fields.Selection(
        selection=[
            ("dd_success", "The direct debit transaction happened"),
            ("dd_failed", "The direct debit transaction didn't happen yet"),
        ],
        string="Direct Debit Transaction Status",
        required=True,
    )

    def action_cancel(self):
        self.ensure_one()
        super_stream = self.l10n_au_super_stream_id
        if self.l10n_au_cancel_type == "dd_success":
            super_stream.action_cancel(force_refund=True)
        elif self.l10n_au_cancel_type == "dd_failed":
            super_stream.action_cancel(force_cancel=True)
        return {
            "type": "ir.actions.act_window_close"
        }
