# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class IrActionsServer(models.Model):
    _inherit = 'ir.actions.server'

    state = fields.Selection(
        selection_add=[
            ('documents_account_record_create', 'New Journal Entry'),
        ],
        ondelete={
            'documents_account_record_create': 'cascade',
        }
    )
    documents_account_create_model = fields.Selection([
        ('account.move.in_invoice', 'Vendor Bill'),
        ('account.move.out_invoice', 'Customer Invoice'),
        ('account.move.in_refund', 'Vendor Credit Note'),
        ('account.move.out_refund', 'Credit Note'),
        ('account.move.entry', 'Miscellaneous Operations'),
        ('account.bank.statement', 'Bank Statement'),
        ('account.move.in_receipt', 'Purchase Receipt'),
    ])
    documents_account_journal_id = fields.Many2one(
        comodel_name='account.journal',
        domain="['|', ('id', 'in', documents_account_suitable_journal_ids), ('id', '=', False)]",
        compute="_compute_documents_account_journal_id", store=True, readonly=False,
    )
    documents_account_suitable_journal_ids = fields.Many2many(
        'account.journal', compute='_compute_documents_account_suitable_journal_ids')
    documents_account_move_type = fields.Char(compute='_compute_documents_account_move_type')

    @api.constrains('model_id', 'state')
    def _check_document_account_check_model(self):
        document_model_id = self.env['ir.model']._get('documents.document')
        for action in self:
            if action.state == 'documents_account_record_create' and action.model_id != document_model_id:
                raise ValidationError(_('"New Journal Entry" can only be applied to Document.'))

    @api.depends('model_id')
    def _compute_allowed_states(self):
        super()._compute_allowed_states()
        document_model_id = self.env['ir.model']._get('documents.document')
        for action in self:
            if action.model_id != document_model_id:
                action.allowed_states = [
                    state
                    for state in action.allowed_states
                    if state != 'documents_account_record_create']

    @api.depends('documents_account_create_model')
    def _compute_documents_account_journal_id(self):
        for action in self:
            if (action.documents_account_journal_id
                    and action.documents_account_journal_id not in action.documents_account_suitable_journal_ids):
                action.documents_account_journal_id = (
                    action.documents_account_suitable_journal_ids[0] if action.documents_account_suitable_journal_ids
                    else False)

    @api.depends('documents_account_create_model')
    @api.depends_context('company')
    def _compute_documents_account_suitable_journal_ids(self):
        company_journals = self.env['account.journal'].search(
            self.env['account.journal']._check_company_domain(self.env.company))
        if not company_journals:
            self.documents_account_suitable_journal_ids = False
            return
        bank_journals = company_journals.filtered(lambda journal: journal.type in ('bank', 'credit'))
        self.documents_account_suitable_journal_ids = False
        for action in self:
            if action.documents_account_move_type == 'statement':
                action.documents_account_suitable_journal_ids = bank_journals
            elif action.documents_account_move_type:
                action.documents_account_suitable_journal_ids = (
                        self.env['account.move']._get_suitable_journal_ids(action.documents_account_move_type))

    @api.depends('documents_account_create_model')
    def _compute_documents_account_move_type(self):
        self.documents_account_move_type = False
        for action in self:
            create_model = action.documents_account_create_model or ''
            if create_model.startswith(('account.move', 'account.bank.statement')):
                action.documents_account_move_type = create_model.split('.')[-1]

    def _generate_action_name(self):
        self.ensure_one()
        if self.state != 'documents_account_record_create':
            return super()._generate_action_name()
        options = dict(self._fields["documents_account_create_model"]._description_selection(self.env))
        translated_model_name = options.get(self.documents_account_create_model, "")
        if self.documents_account_journal_id:
            return _('Create %(model_name)s (%(journal_name)s)',
                     model_name=translated_model_name,
                     journal_name=self.documents_account_journal_id.name or '')
        return _('Create %(model_name)s', model_name=translated_model_name)

    def _name_depends(self):
        return super()._name_depends() + ["documents_account_create_model", "documents_account_journal_id.name"]

    def _run_action_documents_account_record_create_multi(self, eval_context=None):
        documents = eval_context.get('records') or eval_context.get('record')
        if not documents:
            return False

        journal_id = self.documents_account_journal_id or None
        if self.documents_account_create_model.startswith('account.move'):
            return documents.account_create_account_move(self.documents_account_move_type, journal_id=journal_id)
        elif self.documents_account_create_model == 'account.bank.statement':
            return documents.account_create_account_bank_statement(journal_id=journal_id)
        raise NotImplementedError
