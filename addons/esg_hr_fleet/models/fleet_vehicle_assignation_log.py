from odoo import fields, models


class FleetVehicleAssignationLog(models.Model):
    _inherit = "fleet.vehicle.assignation.log"

    company_id = fields.Many2one("res.company", related="vehicle_id.company_id")
