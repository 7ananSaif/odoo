import unicodedata

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools import escape_psql

from odoo.addons.mail.tools.discuss import Store

"""
    █
    █
    █
┌────────────────────────┐
│ ██████████████████████ │
│ █      10:22 PM      █ │
│ █     YO LA TEAM     █ │
│ ██████████████████████ │  T9 "ENCODING" (ITU E.161)
│                        │  =========================
│ ╔══════╦══════╦══════╗ │
│ ║  1   ║  2   ║  3   ║ │  Each letter of the Latin alphabet is mapped to a
│ ║      ║ ABC  ║ DEF  ║ │  number, which is used to encode a word using only
│ ╠══════╬══════╬══════╣ │  digits, like on an old cell phone keypad.
│ ║  4   ║  5   ║  6   ║ │
│ ║ GHI  ║ JKL  ║ MNO  ║ │
│ ╠══════╬══════╬══════╣ │
│ ║  7   ║  8   ║  9   ║ │
│ ║ PQRS ║ TUV  ║ WXYZ ║ │
│ ╠══════╬══════╬══════╣ │
│ ║  *   ║  0   ║  #   ║ │
│ ║      ║      ║      ║ │
│ ╚══════╩══════╩══════╝ │
└────────────────────────┘
"""
T9_MAPPING = {
    letter: digit
    for letters, digit in [
        ("abc", "2"),
        ("def", "3"),
        ("ghi", "4"),
        ("jkl", "5"),
        ("mno", "6"),
        ("pqrs", "7"),
        ("tuv", "8"),
        ("wxyz", "9"),
    ]
    for letter in letters
}

LIGATURES = {
    "Æ": "Ae",
    "æ": "ae",
    "Œ": "Oe",
    "œ": "oe",
    "Ĳ": "IJ",
    "ĳ": "ij",
}


def expand_ligatures(text):
    for ligature, replacement in LIGATURES.items():
        text = text.replace(ligature, replacement)
    return text


def unaccent(text):
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if unicodedata.category(c) != "Mn"
    )


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner", "voip.country.code.mixin", "voip.queue.mixin"]

    t9_name = fields.Char(
        compute="_compute_t9_name",
        export_string_translation=False,
        help=(
            "The partner's name, encoded as the digits that correspond to the letters on an old cell phone keypad.\n"
            "Useful for searching for partners based on this field.\n"
            "Spaces are preserved, characters that can't be encoded are replaced with an 'x'.\n"
            "T9 stands for Text on 9 keys, it comes from the name of the original technology on old cell phones."
        ),
        store=True,
    )

    @api.depends("name")
    def _compute_t9_name(self):
        def encode(letter):
            if letter in T9_MAPPING:
                return T9_MAPPING[letter]
            if letter in "0123456789 ":
                return letter
            return "x"

        for partner in self:
            if not partner.name:
                partner.t9_name = False
                continue
            normalized_name = expand_ligatures(unaccent(partner.name)).casefold()
            partner.t9_name = "".join(encode(letter) for letter in normalized_name)
            # Add a space at the beginning so you can search for matches at the
            # beginning of each word using a pattern like '% 234%'.
            partner.t9_name = " " + partner.t9_name

    @api.model
    def get_contacts(self, offset, limit, search_terms, t9_search=False):
        domain = Domain("phone", "!=", False)
        if search_terms:
            escaped_search_terms = escape_psql(search_terms)
            subdomain = Domain.OR([
                [("complete_name", "ilike", escaped_search_terms)],
                [("email", "ilike", escaped_search_terms)],
            ])
            if len(search_terms) >= self._phone_search_min_length:
                subdomain |= Domain("phone_mobile_search", "like", escaped_search_terms)
            if t9_search:
                subdomain = Domain.OR([subdomain, [("t9_name", "ilike", f" {escaped_search_terms}")]])
            domain = Domain.AND([domain, subdomain])
        contacts = self.search(domain, offset=offset, limit=limit)
        return Store().add(contacts, self._voip_get_store_fields()).get_result()

    def _voip_get_store_fields(self):
        return [
            "commercial_company_name",
            "email",
            "function",
            "is_company",
            "name",
            "phone",
            Store.One("phone_country_id", self.env["res.country"]._voip_get_store_fields()),
            "t9_name",
        ]
