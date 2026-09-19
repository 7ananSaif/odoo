from odoo import api, models
from odoo.addons.mail.tools.discuss import Store


class ResCountry(models.Model):
    _inherit = "res.country"

    @api.model
    def _get_country_by_country_code(self, country_code):
        country = self.search([("code", "=ilike", country_code)], limit=1)
        store = Store()
        return {
            "countryId": country.id,
            "storeData": store.add(country, country._voip_get_store_fields()).get_result(),
        }

    @api.model
    def _voip_get_store_fields(self):
        return ["name", "code", "phone_code", "image_url"]
