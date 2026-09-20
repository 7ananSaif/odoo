from odoo import models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _run_wkhtmltopdf(self, *args, **kwargs):
        # For the audit reports, we want all pages and account reports to have
        # the same margins. To ensure this, we remove any custom paper format
        # arguments when generating PDFs, so that the audit report's default
        # paperformat is applied (see: `get_paperformat`).
        if self.env.context.get('page_format') == 'audit_report':
            kwargs['specific_paperformat_args'] = None
        return super()._run_wkhtmltopdf(*args, **kwargs)

    def get_paperformat(self):
        # For the audit reports, we want all pages and account reports to have
        # the same dimensions, margins, dpi, zoom level, etc. To achieve this,
        # we override the `get_paperformat` function to set the paperformat to use.
        if self.env.context.get('page_format') == 'audit_report':
            return self.env['report.paperformat'].new({
                'name': 'A4 - Audit Report',
                'format': 'A4',
                'orientation': 'Portrait',
                'margin_top': 12,
                'margin_bottom': 12,
                'margin_left': 8,
                'margin_right': 8,
                'css_margins': False,
                'dpi': 96,
                'disable_shrinking': False,
            })
        return super().get_paperformat()
