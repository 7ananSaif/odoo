from odoo import models, api


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    @api.model
    def _create_dian_mail_templates(self):
        """ This function is needed to create the DIAN mail templates because `copy_data` is overridden
        in mail, ignoring the default name passed when calling `copy`.

        This method should be idempotent, because it is called each time the module is updated.
        """
        dian_subject = (
            "{{ object.company_id.partner_id._get_vat_without_verification_code() }};"
            "{{ object.company_id.name }};{{ object.name }};{{ (object.l10n_co_edi_type or '') }};"
            "{{ object.company_id.partner_id.l10n_co_edi_commercial_name }}"
        )

        invoice_template = self.env.ref('account.email_template_edi_invoice', raise_if_not_found=False)
        invoice_template_co_xmlid = 'l10n_co_dian.email_template_edi_invoice'
        if invoice_template and not self.env.ref(invoice_template_co_xmlid, raise_if_not_found=False):
            invoice_dian_template = invoice_template.copy({"subject": dian_subject})
            invoice_dian_template.name = "Invoice (DIAN): Sending"
            self.env['ir.model.data']._update_xmlids([{
                'xml_id': invoice_template_co_xmlid,
                'record': invoice_dian_template,
                'noupdate': True,
            }])

        credit_note_template = self.env.ref('account.email_template_edi_credit_note', raise_if_not_found=False)
        credit_note_template_co_xmlid = 'l10n_co_dian.email_template_edi_credit_note'
        if credit_note_template and not self.env.ref(credit_note_template_co_xmlid, raise_if_not_found=False):
            credit_note_dian_template = credit_note_template.copy({"subject": dian_subject})
            credit_note_dian_template.name = "Credit Note (DIAN): Sending"
            self.env['ir.model.data']._update_xmlids([{
                'xml_id': credit_note_template_co_xmlid,
                'record': credit_note_dian_template,
                'noupdate': True,
            }])
