# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.addons.mail.tools.discuss import Store


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _thread_to_store(self, store: Store, fields, *, request_list=None):
        super()._thread_to_store(store, fields, request_list=request_list)
        if request_list:
            can_send_whatsapp = self.env["whatsapp.template"]._can_use_whatsapp(self._name)
            store.add(self, {"canSendWhatsapp": can_send_whatsapp}, as_thread=True)
