from odoo import models


class UomUom(models.Model):
    _inherit = 'uom.uom'

    def _unprotected_uom_xml_ids(self):
        # Call super to get the original list, then remove 'product_uom_hour'
        # When Planning App is installed, we also need to protect the hour UoM
        # from deletion (and warn in case of modification)
        xml_ids = super()._unprotected_uom_xml_ids()
        return [xml_id for xml_id in xml_ids if xml_id != "product_uom_hour"]
