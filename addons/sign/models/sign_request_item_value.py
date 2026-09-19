# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class SignRequestItemValue(models.Model):
    _name = 'sign.request.item.value'
    _description = "Signature Item Value"
    _rec_name = 'sign_request_id'

    sign_request_item_id = fields.Many2one('sign.request.item', string="Signature Request item", required=True,
                                           index=True, ondelete='cascade')
    sign_item_id = fields.Many2one('sign.item', string="Signature Item", required=True, ondelete='cascade')
    sign_request_id = fields.Many2one(string="Signature Request", required=True, ondelete='cascade', related='sign_request_item_id.sign_request_id')

    value = fields.Text()
    frame_value = fields.Text()
    frame_has_hash = fields.Boolean()

    @api.model
    def _is_number(self, value_str):
        try:
            float(value_str)
            is_number = True
        except ValueError:
            is_number = False
        return is_number

    def write(self, vals):
        for request_item_value in self:
            if updated_value := vals.get("value"):
                value_is_updated = request_item_value.sign_item_id.constant and updated_value != request_item_value.value
                if value_is_updated and self._is_number(updated_value) and self._is_number(request_item_value.value):
                    value_is_updated = float_compare(float(updated_value), float(request_item_value.value), precision_digits=2)
                if value_is_updated:
                    raise UserError(_("Cannot update the value of a read-only sign item"))
        return super().write(vals)
