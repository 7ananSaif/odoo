from odoo import api, fields, models
from odoo.tools import float_compare


class AccountMove(models.Model):
    _inherit = 'account.move'

    esg_emissions_value = fields.Float(string='Emissions (kgCO₂e)', compute='_compute_esg_emissions_value')
    esg_show_emissions_button = fields.Boolean(compute='_compute_esg_show_emissions_button')

    @api.depends('move_type', 'state', 'invoice_line_ids.esg_emission_factor_id', 'invoice_line_ids.quantity', 'invoice_line_ids.account_type')
    def _compute_esg_show_emissions_button(self):
        for move in self:
            move.esg_show_emissions_button = bool(
                move.state == 'posted'
                and any(
                    line.esg_emission_factor_id
                    and float_compare(line.quantity, 0, precision_digits=8) > 0
                    and line.account_type in self.env['account.account'].ESG_VALID_ACCOUNT_TYPES
                    for line in move.invoice_line_ids
                )
            )

    @api.depends('invoice_line_ids.esg_emissions_value', 'invoice_line_ids.quantity')
    def _compute_esg_emissions_value(self):
        for move in self:
            move.esg_emissions_value = sum(line.esg_emissions_value for line in move.invoice_line_ids if float_compare(line.quantity, 0, precision_digits=8) > 0)

    def action_view_move_emissions(self):
        self.ensure_one()
        return {
            'name': self.env._('Emissions of %(move_name)s', move_name=self.name),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,kanban,graph,pivot',
            'res_model': 'esg.carbon.emission.report',
            'domain': [('move_id', '=', self.id)],
        }

    def copy(self, default=None):
        context_self = self.with_context(auto_generate_esg_assignation_rule=False)
        return super(AccountMove, context_self).copy(default)
