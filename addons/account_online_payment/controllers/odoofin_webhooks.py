from odoo.http import Controller, request, route


class OdooFinWebhooksController(Controller):

    @route('/webhook/odoofin/payment_activated', type='jsonrpc', auth='public', methods=['POST'])
    def payments_activated(self):
        data = request.get_json_data()
        if link := request.env['account.online.link'].sudo().search([('client_id', '=', data.get('client_id'))], limit=1):
            if template := request.env(su=True).ref('account_online_payment.mail_template_account_payment_activation_success', raise_if_not_found=False):
                template.send_mail(link.id, force_send=True, email_values={'email_to': link.renewal_contact_email, 'email_from': link.renewal_contact_email})
            link.is_payment_activated = True
        return True
