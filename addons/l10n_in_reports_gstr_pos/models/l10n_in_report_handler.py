# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class L10n_InReportHandler(models.AbstractModel):
    _inherit = 'l10n_in.report.handler'

    def _get_invalid_no_hsn_line_domain(self):
        domain = super()._get_invalid_no_hsn_line_domain()
        domain += [
            "|",
            "&",
                ("move_id.pos_session_ids", "!=", False),
                ("product_uom_id", "!=", False),
            ("move_id.pos_session_ids", "=", False),
        ]
        return domain
