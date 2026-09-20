# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class SignItemRole(models.Model):
    _name = 'sign.item.role'
    _description = "Signature Item Role"
    _rec_name = "name"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    default = fields.Boolean(required=True, default=False)
    sequence = fields.Integer(string="Default order", default=10)

    auth_method = fields.Selection(string="Extra Authentication Step", selection=[
        ('sms', 'Unique Code via SMS')
    ], default=False, help="Force the signatory to identify using a second authentication method")

    change_authorized = fields.Boolean('Change Authorized', help="If checked, recipient of a document with this role can be changed after having sent the request. Useful to replace a signatory who is out of office, etc.")
    assign_to = fields.Many2one(
        'res.partner',
        string='Assign to',
        help="assign the current user or the customer as a signer by default",
    )

    def write(self, vals):
        vals.pop('default', None)
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_role(self):
        for role in self:
            if role.default:
                raise AccessError(_("The role %s is required by the Sign application and cannot be deleted.", role.name))
