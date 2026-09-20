from odoo import Command, api, fields, models


class EmployeeCommutingEmissionsWizard(models.TransientModel):
    _name = "employee.commuting.emissions.wizard"
    _description = "Generate emitted emissions from employee commuting"

    date_start = fields.Date("Emissions Period", required=True)
    date_end = fields.Date(required=True, export_string_translation=False)
    conflicting_emission_ids = fields.Many2many("esg.other.emission", compute="_compute_conflicting_emission_ids", export_string_translation=False)

    @api.depends("date_start", "date_end")
    def _compute_conflicting_emission_ids(self):
        for wizard in self:
            if not wizard.date_start or not wizard.date_end:
                wizard.conflicting_emission_ids = [Command.clear()]
                continue

            overlapping_emissions = self.env["esg.other.emission"].search([
                ("is_fleet", "=", True),
                ("date", "<=", wizard.date_end),
                ("date_end", ">=", wizard.date_start),
            ])
            wizard.conflicting_emission_ids = overlapping_emissions

    def _get_total_commuting_emissions(self):
        self.ensure_one()
        if not self.date_start or not self.date_end:
            return 0.0

        total_co2 = 0.0
        logs = self.env["fleet.vehicle.assignation.log"].search([
            ("company_id", "=", self.env.company.id),
            ("date_start", "<=", self.date_end),
            "|",
                ("date_end", ">=", self.date_start),
                ("date_end", "=", False),
        ])

        version_map = {cv.id: cv for cv in logs.mapped("driver_employee_id.current_version_id")}
        vehicle_map = {v.id: v for v in logs.mapped("vehicle_id")}

        for log in logs:
            employee = log.driver_employee_id
            if not employee:
                continue

            version = version_map.get(employee.current_version_id.id)
            vehicle = vehicle_map.get(log.vehicle_id.id)
            if not version or not vehicle:
                continue

            overlap_start = max(log.date_start, self.date_start)
            overlap_end = min(log.date_end or self.date_end, self.date_end)

            days = (overlap_end - overlap_start).days + 1
            daily_km = (version.distance_home_work or 0) * 2
            work_ratio = vehicle.company_id.weekly_days_at_office / 7.0

            total_co2 += days * daily_km * work_ratio * vehicle.co2 / 1_000

        return int(total_co2)

    def action_save(self):
        emission_factor = self.env.ref("esg_hr_fleet.employee_commuting_factor")
        self.env["esg.other.emission"].create({
            "name": self.env._("Employee Commuting"),
            "date": self.date_start,
            "date_end": self.date_end,
            "esg_emission_factor_id": emission_factor.id,
            "quantity": self._get_total_commuting_emissions(),
            "note": self.env._(
                "Employee commuting from %(start_date)s to %(end_date)s",
                start_date=fields.Date.to_string(self.date_start),
                end_date=fields.Date.to_string(self.date_end),
            ),
            "is_fleet": True,
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": self.env._("Emission successfully created"),
                "next": {
                    "type": "ir.actions.act_window_close",
                },
            },
        }

    def action_see_conflicting_emissions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "esg.carbon.emission.report",
            "name": self.env._("Conflicting Emissions"),
            "views": [[False, "list"], [False, "form"]],
            "domain": [("id", "in", self.conflicting_emission_ids.ids)],
        }
