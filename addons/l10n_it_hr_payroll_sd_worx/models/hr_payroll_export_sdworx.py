# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from lxml import etree

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date


class L10nITHrPayrollExportSdworx(models.Model):
    _name = "l10n.it.hr.payroll.export.sdworx"
    _inherit = ["hr.work.entry.export.mixin"]
    _description = "Export Work Entries to SDWorx (Italy)"

    eligible_employee_line_ids = fields.One2many(
        "l10n.it.hr.payroll.export.sdworx.employee",
        "export_id",
        string="Eligible Employees",
    )

    @api.model
    def _country_restriction(self):
        return "IT"

    def _generate_line_data(self, employee, day, work_entry_collection):
        work_entry_type = work_entry_collection.work_entries[0].work_entry_type_id
        sdworx_code = work_entry_type.l10n_it_sdworx_code
        if not sdworx_code:
            raise UserError(
                self.env._("The work entry type %s does not have an SD Worx IT code")
                % work_entry_type.name
            )
        hours = int(work_entry_collection.duration / 3600)
        minutes = int((work_entry_collection.duration % 3600) / 60)
        return {
            "CodGiustificativoRilPres": sdworx_code,
            "CodGiustificativoUfficiale": sdworx_code,
            "Data": day.strftime("%Y-%m-%d"),
            "NumOre": hours,
            "NumMinuti": minutes,
            "employee": employee,
        }

    def _generate_export_file(self):
        self.ensure_one()
        if not self.env.company.official_company_code:
            raise UserError(self.env._('There is no SDWorx code defined on the company. Please configure it on the Payroll Settings'))

        if invalid_employees := self.eligible_employee_line_ids.employee_id.filtered(lambda e: not e.l10n_it_sdworx_code):
            raise UserError(self.env._(
                'There is no SDWorx code defined for the following employees:\n %(employee_name)s',
                employee_name='\n'.join(invalid_employees.mapped('name'))
            ))

        employee_map = defaultdict(list)
        for employee_line in self.eligible_employee_line_ids:
            we_by_day_and_code = employee_line._get_work_entries_by_day_and_code(
                limit_start=self.period_start, limit_stop=self.period_stop
            )
            for day, we_by_code in we_by_day_and_code.items():
                for work_entry_collection in we_by_code.values():
                    if not work_entry_collection.work_entries:
                        continue
                    line_data = self._generate_line_data(
                        employee_line.employee_id, day, work_entry_collection
                    )
                    employee_map[employee_line.employee_id] += [line_data]

        employees_data = [
            {
                "employee": employee,
                "transections": transections,
            }
            for employee, transections in employee_map.items()
        ]
        xml_str = self.env["ir.qweb"]._render(
            "l10n_it_hr_payroll_sd_worx.l10n_it_sd_worx_template",
            {"employees_data": employees_data},
        )

        # Prettify XML
        root = etree.fromstring(
            xml_str,
            parser=etree.XMLParser(remove_blank_text=True, resolve_entities=False),
        )
        return etree.tostring(
            root, pretty_print=True, encoding="utf-8", xml_declaration=True
        ).decode()

    def _generate_export_filename(self):
        return "SDWorx_export_%s_%s.xml" % (
            format_date(self.env, self.period_start, date_format="MMMM"),
            self.reference_year,
        )

    def _get_name(self):
        return self.env._("Export to SD Worx (Italy)")


class L10nITHrPayrollExportSdworxEmployee(models.Model):
    _name = "l10n.it.hr.payroll.export.sdworx.employee"
    _inherit = "hr.work.entry.export.employee.mixin"
    _description = 'SDWorx Export Employee Italy'

    export_id = fields.Many2one(
        "l10n.it.hr.payroll.export.sdworx", required=True, ondelete="cascade"
    )
