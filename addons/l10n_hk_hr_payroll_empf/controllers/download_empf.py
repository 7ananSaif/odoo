# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import http
from odoo.http import content_disposition, request


class eMPFReportController(http.Controller):
    @http.route('/l10n_hk_hr_payroll_empf/download_empf_report/<models("ir.attachment"):attachments>', type='http', auth='user')
    def download_empf_report(self, attachments):
        attachments.check_access('read')
        assert all(attachment.res_id and attachment.res_model == 'l10n_hk.empf.contribution.report' for attachment in attachments)
        if len(attachments) == 1:
            return request.make_response(attachments.raw, [
                ('Content-Type', attachments.mimetype),
                ('Content-Length', len(attachments.raw)),
                ('Content-Disposition', content_disposition(attachments.name)),
                ('X-Content-Type-Options', 'nosniff'),
            ])
        else:
            mpf_report = attachments.mapped('res_id')
            assert len(set(mpf_report)) == 1
            report = request.env['l10n_hk.empf.contribution.report'].browse(mpf_report[0])
            if report.payroll_group_id:
                file_name = f"eMPF_{report.scheme_id.registration_number}_{report.payroll_group_id.group_id}_{report.contribution_period_end.strftime('%Y%m%d')}.zip"
            else:
                file_name = f"eMPF_{report.scheme_id.registration_number}_{report.contribution_period_end.strftime('%Y%m%d')}.zip"

            content = attachments._build_zip_from_attachments()
            return request.make_response(content, [
                ('Content-Type', 'zip'),
                ('Content-Length', len(content)),
                ('Content-Disposition', content_disposition(file_name)),
                ('X-Content-Type-Options', 'nosniff'),
            ])
