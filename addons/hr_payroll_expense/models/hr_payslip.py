# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _, Command
from odoo.exceptions import AccessError

import logging


_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    expense_ids = fields.One2many(
        comodel_name='hr.expense',
        inverse_name='payslip_id',
        string='Expenses',
        help="Expenses to reimburse to employee.",
    )
    expenses_count = fields.Integer(compute='_compute_expenses_count', compute_sudo=True)

    def _compute_input_line_ids(self):
        super()._compute_input_line_ids()
        self._update_expense_input_line_ids(search_new_valid_expenses=True)

    @api.depends('expense_ids')
    def _compute_expenses_count(self):
        for payslip in self:
            payslip.expenses_count = len(payslip.expense_ids)

    @api.model
    def _issues_dependencies(self):
        return super()._issues_dependencies() + [
            'expense_ids',
            'struct_id.rule_ids',
            'struct_id.rule_ids.code',
            'struct_id.rule_ids.account_debit',
            'struct_id.rule_ids.account_debit.account_type',
        ]

    def _get_errors_by_slip(self):
        # EXTENDS hr_payroll
        errors_by_slip = super()._get_errors_by_slip()
        draft_slips = self.filtered(lambda ps: ps.state == 'draft')
        for struct, slips in draft_slips.filtered('expense_ids').grouped('struct_id').items():
            expense_rules = struct.rule_ids.filtered(lambda rule: rule.code == 'EXPENSES')
            if not expense_rules:
                for slip in slips:
                    errors_by_slip[slip].append({
                        'message': _('No rule to handle expenses'),
                        'action_text': _("Rules"),
                        'action': struct.rule_ids._get_records_action(),
                        'level': 'danger',
                    })
            elif not expense_rules.filtered(
                lambda rule: rule.account_debit and rule.account_debit.account_type == 'liability_payable'
            ):
                for slip in slips:
                    errors_by_slip[slip].append({
                        'message': _('No debit account for EXPENSES rules'),
                        'action_text': _("Expense rules"),
                        'action': expense_rules._get_records_action(),
                        'level': 'danger',
                    })
        return errors_by_slip

    def action_payslip_cancel(self):
        # Remove the link to the cancelled payslip so it can be linked to another payslip
        # EXTENDS hr_payroll
        res = super().action_payslip_cancel()
        expenses_sudo = self.expense_ids.sudo()
        expenses_sudo.payslip_id = False
        self._update_expense_input_line_ids()
        return res

    def action_payslip_draft(self):
        # We can add the new or previously unlinked expenses to the payslip
        # EXTENDS hr_payroll
        res = super().action_payslip_draft()
        self._link_expenses_to_payslip(clear_existing=False)  # Add the new expenses to the payslip, but keep the already linked ones
        return res

    @api.model_create_multi
    def create(self, vals_list):
        # EXTENDS hr_payroll
        payslips = super().create(vals_list)
        draft_slips = payslips.filtered(lambda p: p.employee_id and p.state == 'draft')
        if not draft_slips:
            return payslips
        draft_slips._link_expenses_to_payslip()
        return payslips

    def write(self, vals):
        # EXTENDS hr_payroll
        res = super().write(vals)
        if 'expense_ids' in vals:
            self._update_expense_input_line_ids()
        if 'input_line_ids' in vals:
            self._update_expenses()
        return res

    def _get_employee_expenses_to_refund_in_payslip(self):
        return self.env['hr.expense'].search([
            ('employee_id', 'in', self.employee_id.ids),
            ('state', 'in', ('approved', 'posted')),
            ('payment_mode', '=', 'own_account'),
            ('refund_in_payslip', '=', True),
            ('payslip_id', '=', False)])

    def _link_expenses_to_payslip(self, clear_existing=True):
        """
        Link expenses to a payslip if the payslip is in draft state and the expense is not already linked to a payslip.
        """
        if not (self.env.is_superuser() or self.env.user.has_group('hr_payroll.group_hr_payroll_user')):
            raise AccessError(_(
                "You don't have the access rights to link an expense to a payslip. You need to be a payroll officer to do that.")
            )

        expenses_sudo = self.sudo()._get_employee_expenses_to_refund_in_payslip()
        # group by employee
        expenses_by_employee = expenses_sudo.grouped('employee_id')
        for slip_sudo in self.sudo():
            payslip_expenses = expenses_by_employee.get(slip_sudo.employee_id, self.env['hr.expense'])
            if not slip_sudo.struct_id.rule_ids.filtered(lambda rule: rule.code == 'EXPENSES'):
                continue
            if slip_sudo.expense_ids and clear_existing:
                slip_sudo.expense_ids = [Command.set(payslip_expenses.ids)]
            elif payslip_expenses:
                slip_sudo.expense_ids = [Command.link(expense.id) for expense in payslip_expenses]

    def _update_expense_input_line_ids(self, search_new_valid_expenses=False):
        """
        Update the payslip input lines to reflect the total amount of the expenses.
        :param bool search_new_valid_expenses:
            If False, will only compute the lines using the expenses already linked to the payslip.
            If True, will take all the expenses that are valid for this payslip (do not link them to the payslip)
        """
        expense_type = self.env.ref('hr_payroll_expense.expense_other_input', raise_if_not_found=False)

        expenses_by_employee_sudo = {}
        if search_new_valid_expenses:
            expenses_by_employee_sudo = self.sudo()._get_employee_expenses_to_refund_in_payslip().grouped('employee_id')

        if not expense_type:
            _logger.warning("The 'hr_payroll_expense.expense_other_input' payslip input type is missing.")
            return  # We cannot do anything without the expense type

        for payslip in self:
            # Sudo to bypass access rights, as we just need to read the expense's total amounts
            expenses_sudo = payslip.sudo().expense_ids
            if expenses_by_employee_sudo:
                employee_expenses_sudo = expenses_by_employee_sudo.get(payslip.employee_id, self.env['hr.expense'])
                if employee_expenses_sudo:
                    del expenses_by_employee_sudo[payslip.employee_id]  # To avoid double assignations
                expenses_sudo += employee_expenses_sudo
            total = sum(expenses_sudo.mapped('total_amount'))
            lines_to_remove = payslip.input_line_ids.filtered(lambda x: x.input_type_id == expense_type)
            input_lines_vals = [Command.delete(line.id) for line in lines_to_remove]
            if total:
                input_lines_vals.append(Command.create({
                    'amount': total,
                    'input_type_id': expense_type.id
                }))
            payslip.input_line_ids = input_lines_vals

    def _update_expenses(self):
        expense_type = self.env.ref('hr_payroll_expense.expense_other_input', raise_if_not_found=False)
        if not expense_type:
            return  # We cannot do anything without the expense type
        for payslip_sudo in self.sudo():
            if not payslip_sudo.input_line_ids.filtered(lambda line: line.input_type_id == expense_type):
                # Sudo to bypass access rights, as we just need to unlink the two models
                payslip_sudo.expense_ids.payslip_id = False

    def action_open_expenses(self):
        return_action = {
            'type': 'ir.actions.act_window',
            'name': _('Reimbursed Expenses'),
            'res_model': 'hr.expense',
        }
        if len(self.expense_ids.ids) > 1:
            return_action.update({
                'view_mode': 'list,form',
                'domain': [('id', 'in', self.expense_ids.ids)],
            })
        else:
            return_action.update({
                'view_mode': 'form',
                'res_id': self.expense_ids.id,
            })
        return return_action
