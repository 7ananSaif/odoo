from markupsafe import Markup
from lxml import html

from odoo import api, models, fields, _


class QRCodePaymentWizard(models.TransientModel):
    _name = "qr.code.payment.wizard"
    _inherit = ["account.return.payment.wizard"]
    _description = "Generic Payment Wizard with QR Code"

    qr_code = fields.Html(compute='_compute_qr_code')

    @api.depends('partner_bank_id', 'communication', 'amount_to_pay')
    def _compute_qr_code(self):
        for wizard in self:
            qr_html = False
            if wizard.partner_bank_id and not wizard.is_recoverable and wizard.communication:
                b64_qr = wizard.partner_bank_id.build_qr_code_base64(
                    amount=wizard.amount_to_pay,
                    free_communication=wizard.communication,
                    structured_communication=wizard.communication,
                    currency=wizard.currency_id,
                    debtor_partner=wizard.partner_id,
                )
                if b64_qr:
                    txt = _('Scan me with your banking app.')
                    qr_html = Markup("""
                        <div class="text-center">
                            <img src="{b64_qr}"/>
                            <p><strong>{txt}</strong></p>
                        </div>
                    """).format(b64_qr=b64_qr, txt=txt)
            wizard.qr_code = qr_html

    def _get_b64_qr_data(self):
        self.ensure_one()
        b64_qr = False
        if self.qr_code:
            tree = html.fromstring(self.qr_code)
            if src_list := tree.xpath('//img/@src'):
                b64_qr = src_list[0]
        return b64_qr
