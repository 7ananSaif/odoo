from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain
from odoo.tools.translate import LazyGettext

from odoo.addons.hr_expense_stripe.utils import format_amount_from_stripe


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    stripe_authorization_id = fields.Char("Stripe Authorization ID", index='btree_not_null', copy=False, readonly=True)
    stripe_transaction_id = fields.Char("Stripe Transaction ID", index='btree_not_null', copy=False, readonly=True)
    card_id = fields.Many2one(
        comodel_name='hr.expense.stripe.card',
        string="Card",
        readonly=True,
        copy=False,
        groups='base.group_user',
        index=True,
    )
    mcc_tag_id = fields.Many2one(comodel_name='product.mcc.stripe.tag', copy=False, readonly=True)
    is_card_expense = fields.Boolean(compute='_compute_is_card_expense', readonly=True, compute_sudo=True)

    @api.ondelete(at_uninstall=False)
    def _prevent_unlinking_card_expense(self):
        """ If deleted, it may be created again by a stripe event anyway, this ensures the data is accepted """
        card_expenses = self.filtered('is_card_expense')
        if card_expenses and not self.env.su:
            raise ValidationError(_("You cannot delete an expense that was created from a Stripe card transaction."))

    @api.depends('card_id')
    def _compute_is_card_expense(self):
        """ Because the `card_id` field is locked behind access rights, we need to have a safe way to know
        if an expense is created from a card payment or not
        """
        for expense in self:
            expense.is_card_expense = bool(expense.card_id)

    def _get_default_responsible_for_approval(self):
        # EXTEND hr_expense to bypass approval for expenses created from a stripe authorization
        self.ensure_one()
        if self.sudo().card_id:
            return self.env['res.users']
        else:
            return super()._get_default_responsible_for_approval()

    def _can_be_autovalidated(self):
        # EXTEND hr_expense to bypass approval for expenses created from a stripe authorization
        return super()._can_be_autovalidated() or bool(self.sudo().card_id)

    def _do_approve(self, check=True):
        # EXTEND hr_expense to bypass approval for expenses created from a stripe authorization
        expenses_from_stripe = self.filtered(lambda exp: exp.sudo().card_id and exp.state in {'submitted', 'draft'})
        for expense in expenses_from_stripe:
            expense.sudo().write({
                'approval_state': 'approved',
                'manager_id': False,
                'approval_date': fields.Date.context_today(expense),
            })
        expenses_from_stripe.update_activities_and_mails()
        super(HrExpense, self - expenses_from_stripe)._do_approve(check)

    def _fetch_create_partner_from_stripe(self, merchant_data):
        """ Helper to create/get a partner from the payload Stripe sent, if there are no tax_id we ignore it as relying on other fields is
            deemed unreliable.
        """
        vendor = False
        if merchant_data['tax_id']:  # Only create vendor if there is a tax_id, which is only in France for now
            vendor = self.env['res.partner'].search(
                domain=[('vat', 'ilike', merchant_data['tax_id'])],
                limit=1,
            )
            if not vendor:
                vendor = self.env['res.partner'].create([{
                    'vat': merchant_data['tax_id'],
                    'name': merchant_data['name'],
                    'zip': merchant_data['postal_code'],
                    'city': merchant_data['city'].capitalize(),
                    'country_id': self.env['res.country'].search([('code', 'ilike', merchant_data['country'])], limit=1).id,
                    'state_id': self.env['res.country.state'].search([('code', 'ilike', merchant_data['state'])], limit=1).id,
                    # We're not setting the website, as it's a potential security risk
                }])
        return vendor

    @api.model
    def _create_from_stripe_authorization(self, auth_object, refusal_reason=None):
        """ Create an expense from a stripe `authorization.request` event, refused if refusal_reason is specified.
        """
        merchant_data = auth_object['merchant_data']
        amount_object = auth_object['pending_request'] or auth_object  # The key is always present, but the value may be empty
        card = self.env['hr.expense.stripe.card'].search([('stripe_id', '=', auth_object['card']['id'])], limit=1)
        if not card:
            raise UserError(_("An Expense card that doesn't exist on the database was used"))

        if self.env['hr.expense'].search([('stripe_authorization_id', '=', auth_object['id'])], limit=1):
            return self._update_from_stripe_authorization(auth_object)
        card = card.with_company(card.company_id)
        domain = Domain('can_be_expensed', '=', True)
        domain &= Domain('stripe_mcc_ids', 'any', [('code', '=', merchant_data['category_code'])])
        default_product = self.env.ref('hr_expense.product_product_no_cost', raise_if_not_found=False)
        product = self.env['product.product'].search(domain, limit=1) or default_product
        if not product:
            raise UserError(_("There is no product available for this expense. Please contact your administrator."))
        vendor = self._fetch_create_partner_from_stripe(merchant_data)

        amount_company_currency = amount_currency = format_amount_from_stripe(amount_object['amount'], card.currency_id)
        merchant_currency = (
            self.env['res.currency'].with_context(active_test=False).search([
                    ('name', '=ilike', amount_object['merchant_currency']),
                ],
                limit=1,
            )
            or card.currency_id
        )
        if merchant_currency and not merchant_currency.active:
            merchant_currency.active = True
        if merchant_currency != card.currency_id:
            amount_currency = format_amount_from_stripe(amount_object['merchant_amount'], merchant_currency)

        mcc_tag = self.env['product.mcc.stripe.tag'].search([('code', '=', merchant_data['category_code'])], limit=1)
        create_dict = {
            'payment_mode': 'company_account',
            'name': merchant_data['name'],
            'employee_id': card.employee_id.id,
            'card_id': card.id,
            'mcc_tag_id': mcc_tag.id,
            'manager_id': False,
            'stripe_authorization_id': auth_object['id'],
            'stripe_transaction_id': False,
            'product_id': product and product.id,
            'total_amount': amount_company_currency,
            'total_amount_currency': amount_currency,
            'currency_id': merchant_currency.id,
            'journal_id': card.journal_id.id,
            'payment_method_line_id': card.payment_method_line_id.id,
            'vendor_id': vendor and vendor.id,
        }
        new_expense = self.env['hr.expense'].with_company(card.company_id).create([create_dict])
        if refusal_reason:
            if isinstance(refusal_reason, LazyGettext):
                refusal_reason = refusal_reason._translate(card.sudo().employee_id.lang)  # pylint: disable=gettext-variable
            new_expense._do_refuse(refusal_reason)
        else:
            new_expense._stripe_create_user_activity()
        return new_expense

    def _update_from_stripe_authorization(self, auth_object):
        """
            Update the expense when the event `issuing_authorization.updated` is received,
            (rare, it means the vendor updated the authorization)
            or when `issuing_authorization.created` is received, following an approved `issuing_authorization.request`
             """
        if not self:
            return

        if auth_object['status'] in {'reversed', 'expired'}:
            self._do_refuse(_("Expense was refused by Stripe, or an error occurred"))
            return

        update_vals = {}
        card = self.card_id
        amount_company_currency = amount_currency = format_amount_from_stripe(auth_object['amount'], card.currency_id)
        merchant_currency = (
            self.env['res.currency'].with_context(active_test=False).search([
                    ('name', '=', auth_object['merchant_currency']),
                ],
                limit=1,
            )
            or card.currency_id
        )
        if not merchant_currency.active:
            merchant_currency.active = True
        if merchant_currency != self.company_currency_id:
            amount_currency = format_amount_from_stripe(auth_object['merchant_amount'], merchant_currency)

        if merchant_currency != self.currency_id:
            update_vals['currency_id'] = merchant_currency.id

        most_recent_expense = self.sorted('date')[-1]
        if len(self) == 1:
            if self.company_currency_id.compare_amounts(amount_company_currency, self.total_amount) != 0:
                update_vals['total_amount'] = amount_company_currency

            if merchant_currency.compare_amounts(amount_currency, self.total_amount_currency) != 0:
                update_vals['total_amount_currency'] = amount_currency
        else:
            all_expenses_total_amount = sum(self.mapped('total_amount'))
            older_expenses = self - most_recent_expense
            if self.company_currency_id.compare_amounts(amount_company_currency, all_expenses_total_amount) != 0:
                update_vals['total_amount'] = amount_company_currency - sum(older_expenses.mapped('total_amount'))

            all_expenses_total_amount_currency = sum(self.mapped('total_amount_currency'))
            if merchant_currency.compare_amounts(amount_currency, all_expenses_total_amount_currency) != 0:
                update_vals['total_amount_currency'] = amount_currency - sum(older_expenses.mapped('total_amount_currency'))

        if not self.vendor_id:
            new_vendor = self._fetch_create_partner_from_stripe(auth_object['merchant_data'])
            if new_vendor:
                update_vals['vendor_id'] = new_vendor.id

        if update_vals:
            most_recent_expense.write(update_vals)

    @api.model
    def _create_from_stripe_transaction(self, tr_object, split_id=False):
        """ Create an expense from the event `issuing_transaction.created` (when it is a direct capture),
        which may happen in rare cases (when you buy something on a plane, there can be no authorization due to a lack of connection)
        """
        merchant_data = tr_object['merchant_data']
        card = self.env['hr.expense.stripe.card'].search([('stripe_id', '=', tr_object['card'])], limit=1)
        if not card:
            raise UserError(_("An Expense card that doesn't exist on the database was used"))
        card = card.with_company(card.company_id)

        domain = Domain('can_be_expensed', '=', True)
        domain &= Domain('stripe_mcc_ids', 'any', [('code', '=', merchant_data['category_code'])])
        product = (
            self.env['product.product'].search(domain)
            or self.env.ref('hr_expense.product_product_no_cost', raise_if_not_found=False)
        )

        vendor = self._fetch_create_partner_from_stripe(tr_object['merchant_data'])

        amount_currency = amount_company_currency = -format_amount_from_stripe(tr_object['amount'], card.currency_id)
        merchant_currency = (
            self.env['res.currency'].with_context(active_test=False).search([
                    ('name', '=ilike', tr_object['merchant_currency']),
                ],
                limit=1,
            )
            or card.currency_id
        )
        if merchant_currency and not merchant_currency.active:
            merchant_currency.active = True
        if merchant_currency != card.currency_id:
            amount_currency = -format_amount_from_stripe(tr_object['merchant_amount'], merchant_currency)
        mcc_tag = self.env['product.mcc.stripe.tag'].search([('code', '=', tr_object['merchant_data']['category_code'])], limit=1)
        authorization = tr_object['authorization'] or {}
        if isinstance(authorization, str):
            authorization = {'id': authorization}

        create_dict = {
            'payment_mode': 'company_account',
            'name': merchant_data['name'],
            'employee_id': card.employee_id.id,
            'card_id': card.id,
            'mcc_tag_id': mcc_tag.id,
            'manager_id': False,
            'currency_id': merchant_currency.id,
            'stripe_authorization_id': authorization.get('id', False),
            'stripe_transaction_id': tr_object['id'],
            'payment_method_line_id': card.payment_method_line_id and card.payment_method_line_id.id,
            'product_id': product.id,
            'total_amount': amount_company_currency,
            'total_amount_currency': amount_currency,
            'vendor_id': vendor and vendor.id,
            'split_expense_origin_id': split_id,
        }
        new_expense = self.env['hr.expense'].with_company(card.company_id).create([create_dict])
        new_expense._stripe_create_user_activity()

    def _update_from_stripe_transaction(self, tr_object):
        """ When the event `issuing_transaction.updated` is received, which shouldn't be common
        or `issuing_transaction.created` (payment is captured)
        """
        self.ensure_one()
        update_vals = {}
        card = self.card_id
        amount_company_currency = amount_currency = -format_amount_from_stripe(tr_object['amount'], card.currency_id)
        merchant_currency = (
            self.env['res.currency'].with_context(active_test=False).search([
                    ('name', '=ilike', tr_object['merchant_currency']),
                ],
                limit=1,
        )
            or card.currency_id
        )
        if not merchant_currency.active:
            merchant_currency.active = True
        if merchant_currency != self.company_currency_id:
            amount_currency = -format_amount_from_stripe(tr_object['merchant_amount'], merchant_currency)

        if merchant_currency != self.currency_id:
            update_vals['currency_id'] = merchant_currency.id

        if self.company_currency_id.compare_amounts(amount_company_currency, self.total_amount) != 0:
            update_vals['total_amount'] = amount_company_currency

        if merchant_currency.compare_amounts(amount_currency, self.total_amount_currency) != 0:
            update_vals['total_amount_currency'] = amount_currency

        if not self.vendor_id:
            new_vendor = self._fetch_create_partner_from_stripe(tr_object['merchant_data'])
            if new_vendor:
                update_vals['vendor_id'] = new_vendor.id

        if not self.stripe_transaction_id:
            update_vals['stripe_transaction_id'] = tr_object['id']

        authorization_id = tr_object['authorization']
        if authorization_id and authorization_id != self.stripe_authorization_id:
            update_vals['stripe_authorization_id'] = authorization_id

        if update_vals:
            self.write(update_vals)

    @api.model
    def _stripe_cancel_expense_or_reverse_move(self, tr_object):
        """ This handles the case where an expense is updated but already had a move """
        if not self:
            raise ValidationError(_("Stripe Credit transfers are not implemented"))
        self.ensure_one()
        transaction_amount = -format_amount_from_stripe(tr_object['amount'], self.company_currency_id)
        transaction_amount_in_currency = -format_amount_from_stripe(tr_object['merchant_amount'], self.currency_id)
        remaining_amount = self.total_amount - transaction_amount
        remaining_amount_in_currency = self.total_amount_currency - transaction_amount_in_currency
        move = self.account_move_id
        if move:
            move._reverse_moves(cancel=True)
        self._do_refuse(_("Expense was refunded by vendor"))
        if not self.company_currency_id.is_zero(remaining_amount):
            self.copy({
                'manager_id': False,
                'stripe_transaction_id': tr_object['id'],
                'total_amount': remaining_amount,
                'total_amount_currency': remaining_amount_in_currency,
                'split_expense_origin_id': self.id,
            })

    def _stripe_create_user_activity(self):
        """ Creates an activity to remind the employee they have to upload the payment receipt """
        for expense in self.filtered(lambda exp: exp.card_id and exp.state != 'refused'):
            expense.activity_schedule(
                act_type_xmlid='hr_expense_stripe.mail_act_expense_add_receipt',
                date_deadline=fields.Date.context_today(expense),
                summary=_("Please upload the receipt."),
                user_id=expense.employee_id.user_id.id,
            )

    def _reconcile_stripe_payments(self, existing_statement_lines=False):
        """ When an expense paid by the company is posted, its payment could be reconciled with the bank statement line if it already exists
        """
        expenses_per_stripe_transaction_id = self.grouped('stripe_transaction_id')
        if not existing_statement_lines:
            existing_statement_lines = dict(self.env['account.bank.statement.line']._read_group(
                domain=[('stripe_id', 'in', tuple(expenses_per_stripe_transaction_id.keys()))],
                groupby=['stripe_id'],
                aggregates=['id:recordset'],
            ))
        for stripe_transaction_id, statement_line in existing_statement_lines.items():
            expenses_for_transaction = expenses_per_stripe_transaction_id[stripe_transaction_id]
            if any(statement_line.mapped('is_reconciled')) or any(expense.state != 'paid' for expense in expenses_for_transaction):
                # Skipping automation of tricky corner cases
                continue
            moves_to_reconcile = expenses_for_transaction.account_move_id
            statement_line.set_line_bank_statement_line(moves_to_reconcile.line_ids.filtered(lambda line: line.account_id.reconcile))

    def write(self, vals):
        if 'is_card_expense' in vals:
            raise UserError(_("You cannot edit the security fields of an expense manually"))
        return super().write(vals)

    def action_open_stripe_card(self):
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.expense.stripe.card',
            'target': 'current',
        }
        if len(self) > 1:
            action.update({
                'name': _("Stripe Cards"),
                'view_mode': 'list,form',
                'domain': [('id', 'in', self.card_id.ids)],
            })
        else:
            action.update({
            'name': _("Stripe Card"),
            'view_mode': 'form',
            'res_id': self.card_id.id,
        })
        return action

    def action_submit(self):
        # EXTEND hr_expense
        if any(expense for expense in self if expense.state == 'draft' and expense.stripe_authorization_id and not expense.stripe_transaction_id):
            raise UserError(self.env._("You cannot submit an expense that is reserved. Please wait for the transaction to be captured."))
        return super().action_submit()

    def action_split_wizard(self):
        # EXTEND hr_expense
        self.ensure_one()
        if self.state == 'draft' and self.stripe_authorization_id and not self.stripe_transaction_id:
            raise UserError(self.env._("You cannot split an expense that is reserved. Please wait for the transaction to be captured."))
        return super().action_split_wizard()
