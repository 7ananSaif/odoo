from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class DocumentsAccess(models.Model):
    _name = 'documents.access'
    _description = 'Document / Partner'
    _log_access = False

    document_id = fields.Many2one('documents.document', required=True, bypass_search_access=True, index=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)
    role = fields.Selection(
        [('view', 'Viewer'), ('edit', 'Editor')],
        string='Role', required=False, index=True)
    last_access_date = fields.Datetime('Last Accessed On', required=False)
    expiration_date = fields.Datetime('Expiration', index=True)

    _unique_document_access_partner = models.Constraint(
        'unique(document_id, partner_id)',
        "This partner is already set on this document.",
    )
    _role_or_last_access_date = models.Constraint(
        'check (role IS NOT NULL or last_access_date IS NOT NULL)',
        "NULL roles must have a set last_access_date",
    )

    @api.constrains("partner_id")
    def _check_partner_id(self):
        """Avoid to have bad data when the access is created from a public user or in a CRON."""
        forbidden_users = (self.env.ref('base.user_root'), self.env.ref('base.public_user'))
        for access in self:
            if access.partner_id.user_ids in forbidden_users:
                raise ValidationError(_('This user can not be member.'))

    def _prepare_create_values(self, vals_list):
        vals_list = super()._prepare_create_values(vals_list)
        documents = self.env['documents.document'].browse(
            [vals['document_id'] for vals in vals_list])
        documents.check_access('write')
        return vals_list

    def write(self, vals):
        if 'partner_id' in vals or 'document_id' in vals:
            raise AccessError(_('Access documents and partners cannot be changed.'))

        self.document_id.check_access('write')
        return super().write(vals)

    @api.autovacuum
    def _gc_expired(self):
        self.search([('expiration_date', '<=', fields.Datetime.now())], limit=1000).unlink()
