from odoo import fields, models, _


class HrVersion(models.Model):
    _inherit = 'hr.version'

    leave_allocation_id = fields.Many2one('hr.leave.allocation', 'Allocation', readonly=True, groups="hr.group_hr_user", tracking=True)

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals and vals['state'] == 'cancel':
            for record in self.filtered(lambda r: r.leave_allocation_id and r.leave_allocation_id.state != 'refuse'):
                record.leave_allocation_id.write({'state': 'refuse'})
                record.leave_allocation_id.message_post(
                    body=_('Contract has been cancelled.'),
                )
        return res

    def action_list_leaves(self):
        action = self.env["ir.actions.actions"]._for_xml_id("hr_holidays.hr_leave_allocation_action_all")
        action['context'] = {'search_default_employee_id': self.employee_id.id}
        return action
