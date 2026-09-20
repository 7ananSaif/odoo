# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models
from odoo.exceptions import UserError


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    @api.model
    def _get_default_pdf_report_id(self, move):
        """ The Withhold PDF report is considered the default for Ecuadorian
        withholding PDFs, so we set that instead of account_invoice because otherwise
        when we call account.move.send.wizard it changes the `invoice_template_pdf_report_id`
        on the partner if it's not the default.
        """
        if not move._l10n_ec_is_withholding():
            return super()._get_default_pdf_report_id(move)

        action_report = self.env.ref('l10n_ec_edi.l10n_ec_edi_withhold')

        if move._is_action_report_available(action_report, is_invoice_report=False):
            return action_report

        raise UserError(_("There is no template that applies to this move type."))

    @api.model
    def _get_move_constraints(self, move):
        """ Withhold moves are of type entry which will fail the constraint of account.move.send
            Since we are printing one specific report we can ignore this for withhold moves and only
            check for other move types
        """
        if not (move._l10n_ec_is_withholding() and move.state == 'posted'):
            return super()._get_move_constraints(move)

    @api.model
    def _check_invoice_report(self, moves, **custom_settings):
        """ Withholds use a different PDF report that is not of type is_invoice_report, so we need
        to override the method to tell _is_action_report_available that we don't care if it's an
        invoice report.
        All other moves are passed to the super.
        """
        withhold_moves = moves.filtered(lambda move: move._l10n_ec_is_withholding())
        if (
            custom_settings.get('pdf_report')
            and any(
                not move._is_action_report_available(custom_settings['pdf_report'], is_invoice_report=False)
                for move in withhold_moves
            )
        ):
            raise UserError(_("The sending of withholdings is not set up properly, make sure the report used exists."))

        rest = moves - withhold_moves
        super()._check_invoice_report(rest)
