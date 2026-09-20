# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SignRequestItem(models.Model):
    _inherit = "sign.request.item"

    emsigner_status = fields.Char('emSigner Status', readonly=True, copy=False)
    emsigner_return_value = fields.Char("emSigner Values", readonly=True, copy=False)
    emsigner_transaction_number = fields.Char("emSigner Transaction Number", readonly=True, copy=False)
    emsigner_reference_number = fields.Char("emSigner Reference Number", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        items = super().create(vals_list)
        if not items:
            return items

        for request in items.sign_request_id:
            related_records = items.filtered(lambda r: r.sign_request_id == request)
            emsigner_roles = related_records.filtered(
                lambda r: r.role_id and r.role_id.auth_method == 'emsigner'
            ).role_id

            # If there are multiple emsigner roles or user is doing sign now, we do not set auth_method
            if emsigner_roles:
                if len(emsigner_roles) > 1:
                    emsigner_roles.auth_method = False
                else:
                    emsigner_record = related_records.filtered(
                        lambda r: r.role_id in emsigner_roles
                    )
                    # must have signature items & only one document
                    if emsigner_record and (
                        not emsigner_record._get_current_signature_sign_items()
                        or len(emsigner_record.sign_request_id.template_id.document_ids) > 1
                    ):
                        emsigner_record.role_id.auth_method = False
                    else:
                        # when we have multiple signers, we always keep the emsigner role last in the order
                        # and set the normal signers first
                        normal_signers = related_records - emsigner_record

                        normal_signers = normal_signers.sorted(key=lambda r: r.mail_sent_order or 1)
                        # normal signers first
                        for idx, signer in enumerate(normal_signers, start=1):
                            signer.mail_sent_order = idx

                        # Then emsigners get the last order(s)
                        last_order = len(normal_signers) + 1
                        emsigner_record.mail_sent_order = last_order
        return items

    def _get_current_signature_sign_items(self):
        """ Get the sign items that are of type signature and are assigned to the current role.
        """
        return self.sign_request_id.template_id.sign_item_ids.filtered(
            lambda item: item.responsible_id.id == self.role_id.id and item.type_id.item_type == 'signature'
        )

    def _write_emsigner_data(self, reference_number, transaction_number, return_status):
        self.ensure_one()
        if self.emsigner_status or self.emsigner_transaction_number or self.emsigner_reference_number:
            return
        self.emsigner_status = return_status
        self.emsigner_transaction_number = transaction_number
        self.emsigner_reference_number = reference_number

    def _post_fill_request_item(self):
        for sri in self:
            if sri.role_id.auth_method == 'emsigner' and not sri.emsigner_status and not sri.signed_without_extra_auth:
                raise ValidationError(_("Sign request item is not validated yet."))
        return super()._post_fill_request_item()

    def sign(self, signature, **kwargs):
        if self.role_id.auth_method == 'emsigner':
            return self._sign(signature, validation_required=not self.signed_without_extra_auth, **kwargs)
        return super().sign(signature, **kwargs)
