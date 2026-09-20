# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from markupsafe import Markup, escape


class HrPayrollEditPayslipLinesWizard(models.TransientModel):
    _name = 'hr.payroll.edit.payslip.lines.wizard'
    _description = 'Edit payslip lines wizard'

    payslip_id = fields.Many2one('hr.payslip', required=True, readonly=True)
    line_ids = fields.One2many('hr.payroll.edit.payslip.line', 'edit_payslip_lines_wizard_id', string='Payslip Lines')
    worked_days_line_ids = fields.One2many('hr.payroll.edit.payslip.worked.days.line', 'edit_payslip_lines_wizard_id', string='Worked Days Lines')

    ytd_computation = fields.Boolean(related='payslip_id.ytd_computation')

    def recompute_following_lines(self, line_id):
        self.ensure_one()
        wizard_line = self.env['hr.payroll.edit.payslip.line'].browse(line_id)
        reload_wizard = {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.edit.payslip.lines.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
        if not wizard_line.salary_rule_id:
            return reload_wizard
        localdict = self.payslip_id._get_localdict()
        result_rules_dict = localdict['result_rules']
        remove_lines = False
        lines_to_remove = []
        blacklisted_rule_ids = []
        for line in sorted(self.line_ids, key=lambda x: x.sequence):
            if remove_lines and line.code in self.payslip_id.line_ids.mapped('code'):
                lines_to_remove.append((2, line.id, 0))
            else:
                if line == wizard_line:
                    line._compute_total()
                    remove_lines = True
                blacklisted_rule_ids.append(line.salary_rule_id.id)
                localdict[line.code] = line.total
                result_rules_dict[line.code] = {'total': line.total, 'amount': line.amount, 'quantity': line.quantity, 'rate': line.rate, 'ytd': line.ytd}
                localdict = line.salary_rule_id.category_id._sum_salary_rule_category(localdict, line.total)

        payslip = self.payslip_id.with_context(force_payslip_localdict=localdict, prevent_payslip_computation_line_ids=blacklisted_rule_ids)
        self.line_ids = lines_to_remove + [(0, 0, line) for line in payslip._get_payslip_lines()]
        return reload_wizard

    def recompute_worked_days_lines(self):
        self.ensure_one()
        total_amount = sum(l.amount for l in self.worked_days_line_ids)
        lines = sorted(self.line_ids, key=lambda x: x.sequence)
        if not lines:
            return False
        lines[0].update({
            'amount': total_amount,
            'rate': 100,
            'quantity': 1,
        })
        return self.recompute_following_lines(lines[0].id)

    def action_validate_edition(self):
        today = fields.Date.today()
        old_lines_data = {
            line.salary_rule_id.id: {
                'name': line.name,
                'quantity': line.quantity,
                'rate': line.rate,
                'amount': line.amount,
                'total': line.total,
                'ytd': line.ytd
            }
            for line in self.payslip_id.line_ids
        }
        old_worked_days_data = {
            wd.work_entry_type_id.id: {
                'name': wd.name,
                'number_of_days': wd.number_of_days,
                'number_of_hours': wd.number_of_hours,
                'amount': wd.amount,
                'ytd': wd.ytd,
            }
            for wd in self.payslip_id.worked_days_line_ids
        }
        self.mapped('payslip_id.line_ids').unlink()
        self.mapped('payslip_id.worked_days_line_ids').unlink()
        for wizard in self:
            lines = [(0, 0, line) for line in wizard.line_ids._export_to_payslip_line()]
            worked_days_lines = [(0, 0, line) for line in wizard.worked_days_line_ids._export_to_worked_days_line()]
            wizard.payslip_id.with_context(payslip_no_recompute=True).write({
                'edited': True,
                'line_ids': lines,
                'worked_days_line_ids': worked_days_lines,
                'compute_date': today
            })

            line_fields = {
                'name': _('Name'),
                'quantity': _('Quantity'),
                'rate': _('Rate'),
                'amount': _('Amount'),
                'total': _('Total'),
                'ytd': _('YTD'),
            }
            worked_days_fields = {
                'name': _('Name'),
                'number_of_hours': _('Number of Hours'),
                'number_of_days': _('Number of Days'),
                'amount': _('Amount'),
                'ytd': _('YTD'),
            }
            worked_days_changes = self._generate_changed_values(worked_days_lines, old_worked_days_data, worked_days_fields, 'work_entry_type_id')
            line_changes = self._generate_changed_values(lines, old_lines_data, line_fields, 'salary_rule_id')

            if line_changes or worked_days_changes:
                message_body = Markup('%s<br/>') % _(
                    "This payslip has been manually edited by %(user)s.",
                    user=self.env.user.name
                )
                message_body += worked_days_changes + line_changes
                wizard.payslip_id.message_post(body=message_body)

    def _generate_changed_values(self, new_items, old_data, fields, item):
        changes_list = []
        for new_item in new_items:
            new_item_data = new_item[2]
            old_item_data = old_data.get(new_item_data[item], {})
            changes = []
            line_name = new_item_data['name']

            for field, field_name in fields.items():
                if field == 'ytd' and not self.ytd_computation:
                    continue
                old_value = old_item_data.get(field, None)
                new_value = new_item_data.get(field, None)
                if old_value != new_value:
                    changes.append(Markup('<li><strong>%s: %s → <span class="text-info">%s</span></strong></li>') % (field_name, old_value, new_value))
            if changes:
                changes_list.append(
                    Markup('<li>%s</li><ul>') % (line_name) +
                    Markup('').join(changes) +
                    Markup('</ul>')
                )
        if not changes_list:
            return ''
        if item == 'salary_rule_id':
            message_body = Markup('%s<ul>') % _("Payslip Lines Changes:")
        else:
            message_body = Markup('%s<ul>') % _("Worked Days lines Changes:")
        message_body += Markup('').join(changes_list)
        message_body += Markup('</ul>')
        return message_body


class HrPayrollEditPayslipLine(models.TransientModel):
    _name = 'hr.payroll.edit.payslip.line'
    _description = 'Edit payslip lines wizard line'

    name = fields.Char(translate=True)
    sequence = fields.Integer("Sequence")
    salary_rule_id = fields.Many2one(
        'hr.salary.rule', string='Rule',
        domain="[('struct_id', '=', struct_id)]")
    code = fields.Char(related='salary_rule_id.code')
    version_id = fields.Many2one(related='slip_id.version_id', string='Contract')
    employee_id = fields.Many2one(related='version_id.employee_id', string='Employee')
    rate = fields.Float(string='Rate (%)', digits='Payroll Rate', default=100.0)
    amount = fields.Float(digits='Payroll')
    quantity = fields.Float(digits='Payroll', default=1.0)
    total = fields.Float(compute='_compute_total', string='Total', digits='Payroll', store=True)
    slip_id = fields.Many2one(related="edit_payslip_lines_wizard_id.payslip_id", string='Pay Slip')
    struct_id = fields.Many2one(related="slip_id.struct_id")
    category_id = fields.Many2one(related='salary_rule_id.category_id', readonly=True)
    ytd = fields.Float(string='YTD', digits='Payroll', readonly=True)

    edit_payslip_lines_wizard_id = fields.Many2one('hr.payroll.edit.payslip.lines.wizard', required=True, ondelete='cascade')

    @api.depends('quantity', 'amount', 'rate')
    def _compute_total(self):
        for line in self:
            line.total = float(line.quantity) * line.amount * line.rate / 100

    def _export_to_payslip_line(self):
        return [{
            'sequence': line.sequence,
            'code': line.code,
            'name': line.name,
            'salary_rule_id': line.salary_rule_id.id,
            'version_id': line.version_id.id,
            'employee_id': line.employee_id.id,
            'amount': line.amount,
            'quantity': line.quantity,
            'rate': line.rate,
            'total': line.total,
            'ytd': line.ytd,
            'slip_id': line.slip_id.id
        } for line in self]


class HrPayrollEditPayslipWorkedDaysLine(models.TransientModel):
    _name = 'hr.payroll.edit.payslip.worked.days.line'
    _description = 'Edit payslip line wizard worked days'

    name = fields.Char(related='work_entry_type_id.name')
    slip_id = fields.Many2one(related="edit_payslip_lines_wizard_id.payslip_id", string='PaySlip')
    sequence = fields.Integer("Sequence")
    code = fields.Char(related='work_entry_type_id.code')
    work_entry_type_id = fields.Many2one('hr.work.entry.type')
    number_of_days = fields.Float(string='Number of Days')
    number_of_hours = fields.Float(string='Number of Hours')
    amount = fields.Float(string='Amount')
    ytd = fields.Float(string='YTD', digits='Payroll', readonly=True)

    edit_payslip_lines_wizard_id = fields.Many2one('hr.payroll.edit.payslip.lines.wizard', required=True, ondelete='cascade')

    def _export_to_worked_days_line(self):
        return [{
            'name': line.name,
            'sequence': line.sequence,
            'code': line.code,
            'work_entry_type_id': line.work_entry_type_id.id,
            'number_of_days': line.number_of_days,
            'number_of_hours': line.number_of_hours,
            'amount': line.amount,
            'ytd': line.ytd,
            'payslip_id': line.slip_id.id
        } for line in self]
