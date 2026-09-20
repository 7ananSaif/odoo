# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, tools


class EditBillableTimeTarget(models.Model):
    _name = "edit.billable.time.target"
    _description = "Edit Billable Time Target wizard from Timesheet for users without employee access"
    _order = "name"
    _auto = False
    _log_access = True

    employee_id = fields.Many2one('hr.employee', readonly=True)
    create_date = fields.Datetime(readonly=True)
    name = fields.Char(readonly=True)
    resource_calendar_id = fields.Many2one('resource.calendar', string="Working Hours", readonly=True)
    billable_time_target = fields.Float(string="Monthly Billing Time Target")
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    department_id = fields.Many2one('hr.department', 'Department', readonly=True)
    job_id = fields.Many2one('hr.job', 'Job Position', readonly=True)
    parent_id = fields.Many2one('hr.employee.public', 'Manager', readonly=True)
    child_ids = fields.One2many('hr.employee.public', 'parent_id', string='Direct subordinates')
    address_id = fields.Many2one('res.partner', 'Work Address', readonly=True)
    work_location_id = fields.Many2one('hr.work.location', 'Work Location', readonly=True)
    work_location_name = fields.Char(related="work_location_id.name", string='Work Location Name', readonly=True)
    timesheet_manager_id = fields.Many2one('res.users', 'Timesheet Approver', readonly=True)
    show_hr_icon_display = fields.Boolean(related="employee_id.show_hr_icon_display")
    hr_icon_display = fields.Selection(related="employee_id.hr_icon_display")
    hr_presence_state = fields.Selection(related='employee_id.hr_presence_state')
    image_128 = fields.Image("Image 128", related='employee_id.image_128', compute_sudo=True)
    avatar_128 = fields.Image("Avatar 128", related='employee_id.avatar_128', compute_sudo=True)
    avatar_1920 = fields.Image("Avatar 1920", related='employee_id.avatar_1920', compute_sudo=True)
    image_1024 = fields.Image("Image 1024", related='employee_id.image_1024', compute_sudo=True)
    work_email = fields.Char(readonly=True)
    work_phone = fields.Char(readonly=True)
    mobile_phone = fields.Char(readonly=True)
    birthday_public_display_string = fields.Char(related="employee_id.birthday_public_display_string")
    user_id = fields.Many2one('res.users', readonly=True)
    coach_id = fields.Many2one('hr.employee.public', 'Coach', readonly=True)
    member_of_department = fields.Boolean(related="employee_id.member_of_department")
    newly_hired = fields.Boolean(related="employee_id.newly_hired")
    active = fields.Boolean(readonly=True)

    def write(self, vals):
        """ We only allow the user to edit the billable time target of his employees """
        employee_vals = {}
        if 'billable_time_target' in vals:
            employee_vals['billable_time_target'] = vals.pop('billable_time_target')
            self.env.cache._set_field_cache(self, self._fields.get('billable_time_target')).update(dict.fromkeys(self.ids, employee_vals['billable_time_target']))

        self.check_access('write')
        res = True
        if employee_vals:
            res = self.env['hr.employee'].browse(self.ids).sudo().write(employee_vals)
        return res

    def _get_fields(self):
        return 'e.id AS id,e.name AS name,' + ','.join(
            ('v.%s' if name in self.env['hr.version']._fields and self.env['hr.version']._fields[name].store else 'e.%s') % name
            for name, field in self._fields.items()
            if field.store and field.type not in ['many2many', 'one2many'] and name not in ['id', 'name'])

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
                CREATE OR REPLACE VIEW {self._table} AS (
                        SELECT {self._get_fields()}
                          FROM hr_employee e
                          JOIN (
                              SELECT DISTINCT ON (employee_id) *
                              FROM hr_version
                              ORDER BY employee_id, date_version DESC
                          ) v ON v.employee_id = e.id
                    INNER JOIN res_company company
                            ON e.company_id = company.id
                         WHERE company.timesheet_show_rates IS TRUE
                )
            """
        )
