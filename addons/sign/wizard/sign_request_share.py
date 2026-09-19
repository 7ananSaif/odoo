# Part of Odoo. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta

from odoo import _, api, Command, fields, models
from odoo.exceptions import ValidationError


class SignRequestShare(models.TransientModel):
    _name = 'sign.request.share'
    _description = 'Sign request share wizard'

    template_id = fields.Many2one('sign.template', required=True)
    sign_request_id = fields.Many2one('sign.request')

    is_shared = fields.Boolean(required=True)  # Default sharing status for the sign request
    share_link = fields.Char(related="sign_request_id.share_link")
    validity = fields.Date(related="sign_request_id.validity", readonly=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("sign_request_id"):
                template_id = self.env["sign.template"].browse(int(vals.get("template_id")))
                if template_id:
                    if len(template_id.sign_item_ids.mapped('responsible_id')) > 1:
                        raise ValidationError(_("You cannot share this document by link, because it has fields to be filled by different roles. Use Send button instead."))

                    # Creating the sign request on `create` is required in order to be able to generate
                    # a `share_link` when the sign request doesn't already exist
                    vals["sign_request_id"] = self.env["sign.request"].create({
                            'template_id': template_id.id,
                            'request_item_ids': [Command.create({'role_id': template_id.sign_item_ids.responsible_id.id or self.env.ref('sign.sign_item_role_default').id})],
                            'reference': "%s" % (template_id.name),
                            'state': 'shared',
                            'validity': fields.Date.today() + relativedelta(days=template_id.signature_request_validity) if template_id.signature_request_validity else None
                        }).id

                    vals['is_shared'] = True
        return super().create(vals_list)

    def action_copy_and_close(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'sign_share_and_close_action',
            'params': {
                'share_link': self.share_link,
            }
        }

    def action_stop_sharing(self):
        self.ensure_one()
        self.sign_request_id.unlink()
        self.is_shared = False
        return {'type': 'ir.actions.act_window_close'}

    def action_close_request(self):
        self.ensure_one()
        if not self.is_shared and self.sign_request_id:
            # Cleaning up is needed when the wizard is closed and the sign request didn't exist
            # beforehand. This is linked to the behaviour of `create` where we create the sign
            # request if it doesn't exist already.
            self.sign_request_id.unlink()
        return {'type': 'ir.actions.act_window_close'}

    @api.constrains('validity')
    def _check_validity_not_passed(self):
        for record in self:
            if record.validity and record.validity < fields.Date.today():
                raise ValidationError(_(
                    "The sign request validity cannot be set in the past."
                ))
