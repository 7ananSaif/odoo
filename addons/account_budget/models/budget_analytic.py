# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class BudgetAnalytic(models.Model):
    _name = 'budget.analytic'
    _description = "Budget"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Budget Name', required=True)
    parent_id = fields.Many2one(
        string="Revision Of",
        comodel_name='budget.analytic',
        index=True,
        ondelete='cascade',
    )
    children_ids = fields.One2many(
        string="Revisions",
        comodel_name='budget.analytic',
        inverse_name='parent_id',
    )
    user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.user)
    date_from = fields.Date('Start Date', required=True)
    date_to = fields.Date('End Date', required=True)
    state = fields.Selection(
        string="Status",
        selection=[
            ('draft', "Draft"),
            ('confirmed', "Open"),
            ('revised', "Revised"),
            ('done', "Done"),
            ('canceled', "Canceled")
        ],
        required=True, default='draft',
        readonly=True,
        copy=False,
        tracking=True,
    )
    budget_type = fields.Selection(
        string="Budget Type",
        selection=[
            ('revenue', "Revenue"),
            ('expense', "Expense"),
            ('both', "Both"),
        ],
        required=True, default='expense',
        copy=False,
    )
    budget_line_ids = fields.One2many('budget.line', 'budget_analytic_id', 'Budget Lines', copy=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise ValidationError(_("Budget end date may not be before the starting date."))

    @api.constrains('parent_id')
    def _check_parent_id(self):
        for budget in self:
            if budget._has_cycle():
                raise ValidationError(_('You cannot create recursive revision of budget.'))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_draft_or_cancel(self):
        if any(budget.state not in ('draft', 'canceled') for budget in self):
            raise UserError(_("Deletion is only allowed in the Draft and Canceled stages."))

    def action_budget_confirm(self):
        self.parent_id.filtered(lambda b: b.state == 'confirmed').state = 'revised'
        for budget in self:
            budget.state = 'revised' if budget.children_ids else 'confirmed'

    def action_budget_draft(self):
        self.state = 'draft'

    def action_budget_cancel(self):
        self.state = 'canceled'

    def action_budget_done(self):
        self.state = 'done'

    def create_revised_budget(self):
        revised = self.browse()
        for budget in self:
            revised_budget = budget.copy(default={'name': budget._get_revised_budget_name(), 'parent_id': budget.id, 'budget_type': budget.budget_type})
            revised += revised_budget
            budget.message_post(
                body=Markup("%s: <a href='#' data-oe-model='budget.analytic' data-oe-id='%s'>%s</a>") % (
                    _("New revision"),
                    revised_budget.id,
                    revised_budget.name,
                ))
        return revised._get_records_action()

    def _get_revised_budget_name(self):
        """
        Generate revised budget name with "REV(datetime)" format

        :return: Updated budget name.
        """
        self.ensure_one()
        current_time = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        datetime_str = current_time.strftime("%Y-%m-%d %H:%M")

        # Extract existing revision pattern and base name
        match = re.search(r'(.*) - REV\([^)]+\)$', self.name.strip())
        base_name = match.group(1).strip() if match else self.name.strip()
        return f"{base_name} - REV({datetime_str})"

    def action_open_budget_lines(self):
        context = dict(self.env.context)
        if len(self) == 1:
            context['default_budget_analytic_id'] = self.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Budget Lines'),
            'res_model': 'budget.line',
            'view_mode': 'list,pivot,graph',
            'domain': [('budget_analytic_id', 'in', self.ids)],
            'context': context,
        }

    def action_open_budget_report(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Budget Report'),
            'res_model': 'budget.report',
            'view_mode': 'pivot,list,graph',
            'context': {'search_default_budget_analytic_id': self.id},
        }

    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        return self.env['analytic.plan.fields.mixin']._patch_view(arch, view, view_type)  # patch the budget lines list view
