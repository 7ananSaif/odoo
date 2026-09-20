# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class WhatsappTemplateVariable(models.Model):
    _inherit = 'whatsapp.template.variable'

    def _find_value_from_field_chain(self, record):
        """ Finds the value of a field, using `sudo` access if required.
        This method ensures that protected fields in a `sign.request.item` record are fetched using `sudo`, as the default behavior of the WhatsApp module does not use it.
        Fields that are computed using access token can only be accessed by a user belonging to a specific access group.
        If the field is part of the protected fields list, the method will access it with elevated privileges to bypass access restrictions. Otherwise, it defaults to the standard parent method.

        :param record: The record from which to find the field's value
        :return: The value of the specified field
        :rtype: Any
        """
        self.ensure_one()
        if record._name == "sign.request.item" and self.field_name in record._get_sudo_access_fields():
            return record.sudo(True)._find_value_from_field_path(self.field_name)
        else:
            return super()._find_value_from_field_chain(record)
