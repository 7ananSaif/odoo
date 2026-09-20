import json

from markupsafe import Markup

from odoo import models
from odoo.exceptions import UserError
from odoo.tools import format_date


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def action_submit(self):
        # OVERRIDE of l10n_be_reports
        if self.type_external_id == 'l10n_be_reports.be_vat_return_type' and self.company_id.l10n_be_intervat_mode != 'disabled':
            if not self.company_id._l10n_be_intervat_is_authentication_valid():
                return self.company_id._l10n_be_intervat_authentication_action(self.id, 'submit')

            return self._l10n_be_submit_xml()

        return super().action_submit()

    def l10n_be_action_fetch_from_intervat(self):
        if not self.company_id._l10n_be_intervat_is_authentication_valid():
            return self.company_id._l10n_be_intervat_authentication_action(self.id, 'fetch')

        options = self._get_closing_report_options()
        options['return_id'] = self.id

        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'generate_zip_file_from_intervat',
            }
        }

    def _l10n_be_submit_xml(self):
        att = next(a for a in self.attachment_ids if a.res_name == self.name and a.name.endswith('.xml'))
        try:
            response = self.company_id._l10n_be_post_vat_declaration(att.raw, att.name)
        except UserError as e:
            self._message_log(body=self.env._("Submission Error: \n") + e.args[0])
            self.env.user._bus_send('simple_notification', {
                'type': 'danger',
                'title': self.env._("Submission Error"),
            })
            return 'error'

        if response is None:
            return self.company_id._l10n_be_intervat_authentication_action(self.id, 'submit')

        # We create a new declaration object, so we will be able to fetch the linked documents from
        # MyMinfin API
        new_declaration = self.env['l10n_be.vat.declaration'].create([{
            'pdf_ref': response['pdfReference'],
            'xml_ref': response['xmlReference'],
            'return_id': self.id,
        }])

        # We mark the previous declaration as rectified
        self.env['l10n_be.vat.declaration'].search([
            ('id', '!=', new_declaration.id),
            ('return_id', '=', self.id),
            ('rectification_declaration_id', '=', False),
        ], limit=1).rectification_declaration_id = new_declaration

        self._message_log(body=Markup("""\
        <p>
            %(msg)s:
            <li><strong>PDF</strong>: %(pdf_ref)s</li>
            <li><strong>XML</strong>: %(xml_ref)s</li>
        </p>""") % {
            'msg': self.env._(
                "VAT return of period %(date_from)s -> %(date_to)s has been sent with the following references",
                date_from=Markup("<strong>%s</strong>") % format_date(self.env, self.date_from),
                date_to=Markup("<strong>%s</strong>") % format_date(self.env, self.date_to),
            ),
            'pdf_ref': response['pdfReference'],
            'xml_ref': response['xmlReference'],
        })

        return self._proceed_with_submission()
