from odoo import models


class EventRegistration(models.Model):
    _inherit = 'event.registration'

    def _get_registration_summary(self):
        result = super()._get_registration_summary()

        if self.event_id.badge_format == "96x82":
            badge_printers = self.env["iot.device"].search([("subtype", "=", "label_printer")])
            result['iot_printers'] = badge_printers.mapped(lambda printer: {
                "id": printer.id,
                "name": printer.name,
                "identifier": printer.identifier,
                "iotIdentifier": printer.iot_id.identifier,
                "ip": printer.iot_id.ip,
            })
        else:
            result['iot_printers'] = []

        return result
