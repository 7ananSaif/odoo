from collections import defaultdict
from itertools import product

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools.sql import column_exists, create_column


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    esg_emission_factor_id = fields.Many2one('esg.emission.factor', string='Emission Factor', compute='_compute_esg_emission_factor_id', inverse='_inverse_esg_emission_factor_id', store=True, readonly=False, index='btree_not_null')
    esg_uncertainty_value = fields.Float(string='Uncertainty (%)', related='esg_emission_factor_id.esg_uncertainty_value')
    esg_uncertainty_absolute_value = fields.Float(string='Uncertainty (kgCO₂e)', compute='_compute_esg_uncertainty_absolute_value')
    esg_emission_multiplicator = fields.Float(compute='_compute_esg_emission_multiplicator', store=True, export_string_translation=False)  # Technical field, storing the multiplicator to apply to the gas volumes (important for the report)
    esg_emissions_value = fields.Float(string='Emissions (kgCO₂e)', compute='_compute_esg_emissions_value')

    def _auto_init(self):
        if not column_exists(self.env.cr, "account_move_line", "esg_emission_factor_id"):
            # Create the column to avoid computation during installation
            create_column(self.env.cr, "account_move_line", "esg_emission_factor_id", "int4")
            create_column(self.env.cr, "account_move_line", "esg_emission_multiplicator", "float8")
        return super()._auto_init()

    @api.depends(
        'quantity', 'price_subtotal', 'esg_emission_factor_id.compute_method', 'esg_emission_factor_id.currency_id',
        'esg_emission_factor_id.uom_id', 'product_uom_id', 'currency_id', 'move_type', 'account_type',
    )
    def _compute_esg_emission_multiplicator(self):
        for line in self:
            if line.account_type not in self.env['account.account'].ESG_VALID_ACCOUNT_TYPES or not line.esg_emission_factor_id:
                line.esg_emission_multiplicator = 0
            elif line.esg_emission_factor_id.compute_method == 'monetary':
                aml_currency = line.currency_id or line.company_id.currency_id
                if aml_currency and line.esg_emission_factor_id.currency_id:
                    line.esg_emission_multiplicator = aml_currency._convert(
                        from_amount=line.price_subtotal,
                        to_currency=line.esg_emission_factor_id.currency_id,
                        date=line.date,
                        round=False,
                    )
                else:
                    line.esg_emission_multiplicator = 0
            else:
                aml_uom = line.product_uom_id or line.esg_emission_factor_id.uom_id
                if aml_uom and line.esg_emission_factor_id.uom_id:
                    line.esg_emission_multiplicator = aml_uom._compute_quantity(
                        qty=line.quantity,
                        to_unit=line.esg_emission_factor_id.uom_id,
                        round=False,
                    )
                else:
                    line.esg_emission_multiplicator = 0

            if line.move_type == 'in_refund':
                line.esg_emission_multiplicator *= -1

    @api.depends('esg_emission_multiplicator', 'esg_emission_factor_id.esg_emissions_value')
    def _compute_esg_emissions_value(self):
        for line in self:
            if line.account_type not in self.env['account.account'].ESG_VALID_ACCOUNT_TYPES:
                line.esg_emissions_value = 0
            else:
                line.esg_emissions_value = line.esg_emission_factor_id.esg_emissions_value * line.esg_emission_multiplicator

    @api.depends('esg_emissions_value', 'esg_uncertainty_value')
    def _compute_esg_uncertainty_absolute_value(self):
        for line in self:
            if line.account_type not in self.env['account.account'].ESG_VALID_ACCOUNT_TYPES:
                line.esg_uncertainty_absolute_value = 0
            else:
                line.esg_uncertainty_absolute_value = line.esg_emissions_value * line.esg_uncertainty_value

    @api.depends('product_id', 'account_id', 'partner_id')
    def _compute_esg_emission_factor_id(self):
        move_lines = self.filtered(lambda aml: aml.account_type in self.env['account.account'].ESG_VALID_ACCOUNT_TYPES)
        if move_lines:
            move_lines.with_context(auto_generate_esg_assignation_rule=False)._assign_factors_to_move_lines(no_match_reset=True)

    def _inverse_esg_emission_factor_id(self):
        if not (
            self.env.context.get('auto_generate_esg_assignation_rule', True)
            and (move_lines_with_emission_factor := self.filtered('esg_emission_factor_id'))
        ):
            return
        assignation_vals_list = []
        esg_emission_factor_id_assignation_key = {}
        # domain to search a rule containing the same combinaison (product_id, partner_id, account_id) linked
        # to another emission_factor to remove it since the user breaks it
        assignation_rules_to_remove_domain = Domain.FALSE
        # domain to search the existing assignation rules to avoid creating the same rule
        assignation_rules_to_check_domain = Domain.FALSE
        lines_per_group = defaultdict(self.env['account.move.line'].browse)
        for line in move_lines_with_emission_factor:
            for combinaison in product(*[(v, False) for v in (line.product_id.id, line.partner_id.id, line.account_id.id)]):
                lines_per_group[combinaison] |= line

        expected_nb_matches_per_group = {
            (product_id, partner_id, account_id): 1 + [product_id, partner_id, account_id].count(False)
            for product_id in [True, False]
            for partner_id in [True, False]
            for account_id in [True, False]
            if product_id or partner_id or account_id
        }

        processed_account_move_line_ids = set()
        for (product_bool, partner_bool, account_bool), expected_nb_matches in expected_nb_matches_per_group.items():
            for (product_id, partner_id, account_id), lines in lines_per_group.items():
                if (
                    product_bool != bool(product_id)
                    or partner_bool != bool(partner_id)
                    or account_bool != bool(account_id)
                    or all(line.id in processed_account_move_line_ids for line in lines)
                ):
                    continue
                esg_emission_factor = lines.esg_emission_factor_id
                combination_domain = Domain([
                    ('product_id', '=', product_id),
                    ('partner_id', '=', partner_id),
                    ('account_id', '=', account_id),
                ])
                if len(esg_emission_factor) > 1:
                    # break assignation rules (to remove if exists)
                    assignation_rules_to_remove_domain |= combination_domain
                    continue
                assignation_rules_to_remove_domain |= combination_domain & Domain([
                    ('esg_emission_factor_id', '!=', esg_emission_factor.id),
                ])
                if len(lines) >= expected_nb_matches + 1:
                    processed_account_move_line_ids.update(lines.ids)
                    esg_emission_factor_id_assignation_key[product_id, partner_id, account_id] = esg_emission_factor.id
                    assignation_rules_to_check_domain |= combination_domain
                    continue
                domain = Domain([('esg_emission_factor_id', '!=', False), ('id', 'not in', lines.ids)])
                if product_id:
                    domain &= Domain([('product_id', '=', product_id)])
                if partner_id:
                    domain &= Domain([('partner_id', '=', partner_id)])
                if account_id:
                    domain &= Domain([('account_id', '=', account_id)])
                other_move_lines = self.env['account.move.line'].search(domain, limit=10)
                nb_matches = len(lines) - 1
                for other_line in other_move_lines:
                    if other_line.esg_emission_factor_id == esg_emission_factor:
                        nb_matches += 1
                    if nb_matches >= expected_nb_matches:
                        processed_account_move_line_ids.update(lines.ids)
                        esg_emission_factor_id_assignation_key[product_id, partner_id, account_id] = esg_emission_factor.id
                        assignation_rules_to_check_domain |= combination_domain
                        break
        if not assignation_rules_to_check_domain.is_false():
            assignation_rule_read_group = self.env['esg.assignation.line']._read_group(
                assignation_rules_to_check_domain,
                ['product_id', 'partner_id', 'account_id'],
                ['esg_emission_factor_id:recordset']
            )
            esg_emission_factor_per_rule = {
                (product.id, partner.id, account.id): emission_factors
                for product, partner, account, emission_factors in assignation_rule_read_group
            }
            for (product_id, partner_id, account_id), esg_emission_factor_id in esg_emission_factor_id_assignation_key.items():
                esg_emission_factor = esg_emission_factor_per_rule.get((product_id, partner_id, account_id), self.env['esg.emission.factor'])
                if not esg_emission_factor:
                    assignation_vals_list.append({
                        'product_id': product_id,
                        'partner_id': partner_id,
                        'account_id': account_id,
                        'esg_emission_factor_id': esg_emission_factor_id,
                    })
                    assignation_rules_to_remove_domain |= Domain([
                        ('product_id', '=', product_id),
                        ('partner_id', '=', partner_id),
                        ('account_id', '=', account_id),
                        ('esg_emission_factor_id', '!=', esg_emission_factor_id),
                    ])
                elif esg_emission_factor.id != esg_emission_factor_id:
                    # broken rule, should be removed
                    assignation_rules_to_remove_domain |= Domain([('product_id', '=', product_id), ('partner_id', '=', partner_id), ('account_id', '=', account_id)])
        if not assignation_rules_to_remove_domain.is_false():
            assignation_rules_to_remove = self.env['esg.assignation.line'].search(assignation_rules_to_remove_domain)
            if assignation_rules_to_remove:
                assignation_rules_to_remove.unlink()
        if assignation_vals_list:
            self.env['esg.assignation.line'].create(assignation_vals_list)

    def _assign_factors_to_move_lines(self, factors=None, no_match_reset=False):
        domain = [
            '|', '|',
            ('product_id', 'in', self.product_id.ids),
            ('partner_id', 'in', self.partner_id.ids),
            ('account_id', 'in', self.account_id.ids),
        ]
        if factors:
            domain = Domain.AND([domain, [('esg_emission_factor_id', 'in', factors.ids)]])
        factor_per_rule = {
            (rule.product_id.id, rule.partner_id.id, rule.account_id.id): rule.esg_emission_factor_id.id
            for rule in self.env['esg.assignation.line'].search(domain)
        }

        modified_aml_ids = []
        for line in self:
            initial_rule = (line.product_id.id, line.partner_id.id, line.account_id.id)
            combinations = list(product(*[(v, False) for v in initial_rule]))
            assigned = False
            for rule in combinations:
                if rule in factor_per_rule:
                    line.esg_emission_factor_id = factor_per_rule[rule]
                    modified_aml_ids.append(line.id)
                    assigned = True
                    break
            if not assigned and (no_match_reset or line.esg_emission_factor_id in factors):
                line.esg_emission_factor_id = False
                modified_aml_ids.append(line.id)

        return tuple(modified_aml_ids)
