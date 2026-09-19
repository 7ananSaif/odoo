from odoo import api, fields, models

from odoo.addons.voip.models.utils import extract_country_code


class VoipCountryCode(models.AbstractModel):
    """Mixin to link phone number to a res.country record.

    This mixin extracts the country ISO code (e.g. "be" for Belgium) from the
    international dialing prefix of the phone number (e.g. "+32"), and then link
    to a res.country record. This is useful for displaying country flags or
    identifying the origin of a phone number.

    Models inheriting this mixin should have a phone number field. If the field
    is not named 'phone', they should override `_phone_get_number_fields()`.
    """

    _name = "voip.country.code.mixin"
    _description = "Phone Country Mixin"

    country_code_from_phone = fields.Char(
        compute="_compute_phone_country_id",
        export_string_translation=False,
        help=(
            "Computes the country ISO code (e.g. be for Belgium) from the phone number dialing code (e.g. +32), if any.\n"
            "Useful for displaying the flag associated with a phone number."
        ),
    )
    phone_country_id = fields.Many2one(
        "res.country",
        compute="_compute_phone_country_id",
        export_string_translation=False,
    )

    @api.depends(lambda self: self._phone_get_number_fields())
    def _compute_phone_country_id(self) -> None:
        fields = self._phone_get_number_fields()
        sanitized_fields = [f"{field}_sanitized" for field in fields if "sanitized" not in field]
        sanitized_fields = [field for field in sanitized_fields if field in self]
        self.phone_country_id = False
        self.country_code_from_phone = ""
        countries_by_code = self.env["res.country"].search_fetch([("code", "!=", False)]).grouped("code")
        for record in self:
            for field in [*sanitized_fields, *fields]:
                phone_number = record[field]
                if not phone_number:
                    continue
                iso_code = extract_country_code(phone_number)["iso"]
                if not iso_code:
                    continue
                record.country_code_from_phone = iso_code
                record.phone_country_id = countries_by_code.get(iso_code.upper())
                break
