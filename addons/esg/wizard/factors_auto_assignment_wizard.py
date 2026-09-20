from markupsafe import Markup

from odoo import fields, models
from odoo.fields import Domain


class FactorsAutoAssignmentWizard(models.TransientModel):
    _name = 'factors.auto.assignment.wizard'
    _description = 'Auto-assignment of emission factors to move lines'

    start_date = fields.Date(required=True, help="Correspond to the period to consider for the assignment of the factors to the move lines.")
    end_date = fields.Date()
    replace_previous_factors = fields.Boolean(
        default=False, required=True,
        help="If checked, any emission lines that already have an emission factor (manually or automatically assigned) will be reassigned if a matching factor is found based on your configuration.",
    )

    def action_save(self):
        """Auto assign the emission factors and show the view of updated emissions."""
        self.ensure_one()
        updated_amls = set()
        emission_factors = self.env['esg.emission.factor'].browse(self.env.context.get('active_ids'))
        domain = Domain('date', '>=', self.start_date)
        if self.end_date:
            domain &= Domain('date', '<=', self.end_date)
        if not self.replace_previous_factors:
            domain &= Domain('esg_emission_factor_id', '=', False)

        domain &= Domain('account_id.account_type', 'in', self.env['account.account'].ESG_VALID_ACCOUNT_TYPES)
        move_lines = self.env['account.move.line'].with_context(auto_generate_esg_assignation_rule=False).search(domain)
        updated_amls.update(-id for id in move_lines._assign_factors_to_move_lines(factors=emission_factors))

        if self.env.context.get('from_list_view'):
            # Only redirect to the list of updated emissions when coming from the Emission Factor list view.
            return {
                'name': self.env._("Updated Emissions"),
                'type': 'ir.actions.act_window',
                'view_mode': 'list,kanban,graph,pivot',
                'res_model': 'esg.carbon.emission.report',
                'domain': [('id', 'in', tuple(updated_amls))],
                'help': Markup('<p class="o_view_nocontent_smiling_face">{title}</p>').format(
                    title=self.env._("No emissions were updated."),
                ),
            }
        return None
