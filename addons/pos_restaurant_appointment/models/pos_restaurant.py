# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class RestaurantTable(models.Model):
    _inherit = 'restaurant.table'

    appointment_resource_id = fields.Many2one('appointment.resource', string='Appointment resource', index='btree_not_null')

    @api.model
    def _load_pos_data_fields(self, config):
        data = super()._load_pos_data_fields(config)
        data += ['appointment_resource_id']
        return data

    @api.model_create_multi
    def create(self, vals_list):
        tables = super().create(vals_list)

        for table in tables:
            if not table.appointment_resource_id:
                table.appointment_resource_id = table.env['appointment.resource'].sudo().create({
                    'name': f'Table {table.table_number}',
                    'capacity': table.seats,
                    'pos_table_ids': table,
                    'appointment_type_ids': table.floor_id.pos_config_ids.appointment_type_id,
                })

        return tables

    def write(self, vals):
        res = super().write(vals)

        if 'active' in vals:
            if not vals['active']:
                self.appointment_resource_id.sudo().active = False
            else:
                for table in self:
                    if not table.appointment_resource_id:
                        continue
                    table.appointment_resource_id.sudo().write({
                        'name': f'Table {table.table_number}',
                        'capacity': table.seats,
                    })

        return res

    def unlink(self):
        for table in self:
            table.appointment_resource_id.sudo().unlink()

        return super().unlink()

    @api.ondelete(at_uninstall=True)
    def _delete_linked_resources(self):
        for table in self:
            table.appointment_resource_id.unlink()
