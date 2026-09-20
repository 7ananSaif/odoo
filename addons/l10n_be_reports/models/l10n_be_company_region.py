from odoo import fields, models


""" Mapping may not be 100% correct. Zip code region data obtained from:
    https://opendata.brussels.be/explore/dataset/codes-ins-nis-postaux-belgique/information/
    https://www.bpost.be/fr/outil-de-validation-de-codes-postaux
    Some mappings could be missing.
"""


class BeCompanyRegion(models.Model):
    _name = 'l10n_be.company.region'
    _description = "Belgian Company Region"

    name = fields.Char(string="Name", required=True, translate=True)
    xbrl_code = fields.Char(string="XBRL Code", required=True)
    zip_start = fields.Integer(string="Zip Code Start", required=True)
    zip_end = fields.Integer(string="Zip Code End", required=True)

    _overlap_constraint = models.Constraint(
        "EXCLUDE USING gist (int4range(zip_start, zip_end) WITH &&)",
        "Zip code overlaps with other records",
    )
    _start_end_constraint = models.Constraint(
        "CHECK(zip_start < zip_end)",
        "Start zip code must be less than or equal to end zip code.",
    )
