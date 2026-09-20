from odoo import api, fields, models


class PlanningRole(models.Model):
    _inherit = 'planning.role'

    sync_shift_rental = fields.Boolean(
        "Sync Shifts and Rental Orders",
        help="- Create rental orders for your shifts.\n"
            "- Orders for products linked to this role can’t be confirmed if no resources are available to handle the shifts.\n"
            "- On the website, users can’t select dates when no resources are available.\n"
            "- The order's rental period and the shift dates are synchronized.",
    )
    rental_product_count = fields.Integer(
        compute="_compute_rental_product_count",
        export_string_translation=False,
    )

    @api.depends("product_ids")
    def _compute_rental_product_count(self):
        if not any(self._ids):
            for role in self:
                role.rental_product_count = len(role.product_ids.filtered('rent_ok'))
            return
        rental_product_count_per_role = dict(
            self.env['product.template']._read_group(
                [('planning_role_id', 'in', self.ids), ('rent_ok', '=', True)],
                ['planning_role_id'],
                ['__count'],
            )
        )
        for role in self:
            role.rental_product_count = rental_product_count_per_role.get(role, 0)
