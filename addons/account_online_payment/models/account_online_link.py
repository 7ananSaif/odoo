import logging
from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountOnlineLink(models.Model):
    _inherit = 'account.online.link'

    is_payment_enabled = fields.Boolean()
    is_payment_activated = fields.Boolean()

    def _update_payments_activated(self, data):
        self.ensure_one()

        if data.get('is_payment_enabled') is not None:
            self.is_payment_enabled = data['is_payment_enabled']

        if data.get('is_payment_activated') is not None:
            self.is_payment_activated = data['is_payment_activated']

    def _update_connection_status(self):
        data = super()._update_connection_status()

        self._update_payments_activated(data)

        return data

    def _activate_payments(self):
        self.ensure_one()

        if not self.is_payment_enabled:
            raise UserError(_('To activate payments, you must first enable them when connecting a bank account.'))

        if self.is_payment_activated:
            raise UserError(_('Payments are already activated.'))

        data = {}
        while True:
            response = self._fetch_odoo_fin('/proxy/v1/activate_payments', data)
            next_data = response.get('next_data')
            if not next_data:
                break
            data['next_data'] = next_data

        return {
            'type': 'ir.actions.act_url',
            'url': response['redirect_url'],
            'target': '_blank',
        }

    def action_activate_payments(self):
        self.ensure_one()
        return self._activate_payments()

    def _success_link(self):
        action = super()._success_link()

        try:
            response = self._activate_payments()
            if not response:
                return action

            if template := self.env.ref('account_online_payment.mail_template_account_payment_activation', raise_if_not_found=False):
                template.with_context({'url': response['url']}).send_mail(self.id)

            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.env.user.id,
                summary=_("Complete your KYC"),
                note=_("You haven't completed your KYC yet, so you can't process payment directly from Odoo."),
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'title': _("Time to complete your KYC"),
                    'message': _(
                        "To process payments directly from Odoo, please complete your KYC now: %s. You can also do it later in the bank journal settings."
                    ),
                    'links': [{
                        'label': _("KYC Link"),
                        'url': response['url'],
                    }],
                    'next': action if action else {
                        'type': 'ir.actions.client',
                        'tag': 'soft_reload',
                    }
                }
            }
        except UserError as e:
            _logger.warning("Non-blocking error during payment activation: %s", e)
            return action
