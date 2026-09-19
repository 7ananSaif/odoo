from odoo import models, api, _
from odoo.exceptions import RedirectWarning
from odoo.tools.misc import format_date
from odoo.addons.l10n_nl_reports.wizard.l10n_nl_reports_sbr_tax_report_wizard import SoapClientWrapper

import base64
import json
import os
from dateutil.relativedelta import relativedelta
from markupsafe import Markup
from tempfile import NamedTemporaryFile
from odoo.tools.zeep import wsse
from odoo.tools.zeep.exceptions import Fault


class L10n_Nl_ReportsSbrIcpWizard(models.TransientModel):
    _name = 'l10n_nl_reports.sbr.icp.wizard'
    _inherit = ['l10n_nl_reports.sbr.tax.report.wizard']
    _description = 'L10n NL Intra-Communautaire Prestaties for SBR Wizard'

    @api.depends('date_to', 'date_from', 'is_test')
    def _compute_sending_conditions(self):
        # OVERRIDE
        for wizard in self:
            wizard.can_report_be_sent = (
                wizard.is_test
                or (
                    wizard.env.company.tax_lock_date
                    and wizard.env.company.tax_lock_date >= wizard.date_to
                    and (
                        not wizard.env.company.l10n_nl_reports_sbr_icp_last_sent_date_to
                        or wizard.date_from > wizard.env.company.l10n_nl_reports_sbr_icp_last_sent_date_to
                        or wizard.date_to < wizard.env.company.l10n_nl_reports_sbr_icp_last_sent_date_to + relativedelta(months=1)
                    )
                )
            )

    def action_download_xbrl_file(self):
        options = self.env.context['options']
        options['codes_values'] = self._generate_general_codes_values(options)
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'export_icp_report_to_xbrl',
            }
        }

    def send_xbrl(self):
        # Send the XBRL file to the government with the use of a Zeep client.
        # The wsdl address points to a wsdl file on the government server.
        # It contains the definition of the 'aanleveren' function, which actually sends the message.
        options = self.env.context['options']
        account_return = self.env['account.return']._get_return_from_report_options(options)
        closing_move = account_return.closing_move_ids if account_return else None
        if not self.is_test:
            if not closing_move:
                raise RedirectWarning(
                    _("No closing entry was found for the selected period. Please create one and post it before sending your report."),
                    self.env['account.return'].action_open_tax_return_view(additional_return_domain=[
                        ('date_to', '<=', options['date']['date_to']),
                        ('date_from', '>=', options['date']['date_from']),
                        ('type_id.report_id', '=', options['report_id']),
                    ]),
                    _("Create Closing Entry"),
                )
            if any(move.state == 'draft' for move in closing_move):
                raise RedirectWarning(
                    _("The closing entry for the selected period is still in draft. Please post it before sending your report."),
                    self.env['account.return'].action_open_tax_return_view(additional_return_domain=[
                        ('date_to', '<=', options['date']['date_to']),
                        ('date_from', '>=', options['date']['date_from']),
                        ('type_id.report_id', '=', options['report_id']),
                    ]),
                    _("Closing Entry"),
                )
        options['codes_values'] = self._generate_general_codes_values(options)
        xbrl_data = self.env['l10n_nl_reports.ec.sales.report.handler'].export_icp_report_to_xbrl(options)
        report_file = xbrl_data['file_content']

        serv_root_cert = self.env.company._l10n_nl_get_server_root_certificate_bytes()
        certificate = base64.b64decode(self.env.company.sudo().l10n_nl_reports_sbr_cert_id.pem_certificate)
        private_key = base64.b64decode(self.env.company.sudo().l10n_nl_reports_sbr_cert_id.private_key_id.pem_key)
        try:
            with NamedTemporaryFile(delete=False) as f:
                f.write(serv_root_cert)
            wsdl = 'https://' + ('preprod-' if self.is_test else '') + 'dgp2.procesinfrastructuur.nl/wus/2.0/aanleverservice/1.2?wsdl'
            delivery_client = SoapClientWrapper().create_soap_client(wsdl, f, certificate, private_key)
            factory = delivery_client.type_factory('ns0')
            aanleverkenmerk = wsse.utils.get_unique_id()
            response = delivery_client.service.aanleveren(
                berichtsoort='ICP',
                aanleverkenmerk=aanleverkenmerk,
                identiteitBelanghebbende=factory.identiteitType(nummer=self._get_sbr_identifier(), type='BTW'),
                rolBelanghebbende='Bedrijf',
                berichtInhoud=factory.berichtInhoudType(mimeType='application/xml', bestandsnaam='ICPReport.xbrl', inhoud=report_file),
                autorisatieAdres='http://geenausp.nl',
            )
            kenmerk = response.kenmerk
        except Fault as fault:
            detail_fault = fault.detail.getchildren()[0]
            raise RedirectWarning(
                message=_("The Tax Service returned the following error. Please upgrade your module and try again before submitting a support ticket.") + "\n\n" + detail_fault.find("fault:foutbeschrijving", namespaces={**fault.detail.nsmap, **detail_fault.nsmap}).text,
                action=self.env.ref('base.open_module_tree').id,
                button_text=_("Go to Apps"),
                additional_context={
                    'search_default_name': 'l10n_nl_reports_sbr_icp',
                    'search_default_extra': True,
                },
            )
        finally:
            os.unlink(f.name)

        if not self.is_test:
            self.env.company.sudo().l10n_nl_reports_sbr_icp_last_sent_date_to = self.date_to
            subject = _("ICP report sent")
            body = _(
                "The ICP report from %(date_from)s to %(date_to)s was sent to Digipoort.%(newline)s"
                "We will post its processing status in this chatter once received.%(newline)s"
                "Discussion ID: %(id)s",
                date_from=format_date(self.env, self.date_from),
                date_to=format_date(self.env, self.date_to),
                id=kenmerk,
                newline=Markup("<br>"),
            )
            filename = f'icp_report_{self.date_to.year}_{self.date_to.month}.xbrl'
            closing_move.message_post(subject=subject, body=body, attachments=[(filename, report_file)])
            closing_move.message_subscribe(partner_ids=[self.env.user.id])

        self._additional_processing(options, kenmerk, closing_move)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Sending your report"),
                'type': 'success',
                'message': _("Your ICP report is being sent to Digipoort. Check its status in the closing entry's chatter."),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
