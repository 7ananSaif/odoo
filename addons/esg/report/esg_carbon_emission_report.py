from odoo import api, fields, models, tools
from odoo.exceptions import UserError


class EsgCarbonEmissionReport(models.Model):
    _name = 'esg.carbon.emission.report'
    _description = 'ESG Carbon Emissions Report'
    _auto = False

    date = fields.Date(required=True)
    date_end = fields.Date()
    esg_emission_factor_id = fields.Many2one('esg.emission.factor', string='Emission Factor')
    move_id = fields.Many2one('account.move', string='Journal Entry')
    name = fields.Text()
    note = fields.Text()
    quantity = fields.Integer(required=True)
    esg_emissions_value = fields.Float(string='Emissions (kgCO₂e)')
    esg_uncertainty_absolute_value = fields.Float(string='Uncertainty (kgCO₂e)')
    esg_emissions_value_t = fields.Float(string='tCO₂e')
    esg_uncertainty_value = fields.Float(related='esg_emission_factor_id.esg_uncertainty_value', string='Uncertainty (%)')
    partner_id = fields.Many2one(related='move_id.partner_id')
    source_id = fields.Many2one(related='esg_emission_factor_id.source_id')
    scope = fields.Selection(related='source_id.scope')
    uom_id = fields.Many2one('uom.uom', string='UoM', compute='_compute_uom_id', store=True)
    currency_id = fields.Many2one('res.currency', compute='_compute_currency_id', store=True)
    compute_method = fields.Selection(related='esg_emission_factor_id.compute_method')
    price_subtotal = fields.Monetary(string='Amount', currency_field='currency_id')
    database_id = fields.Many2one(string='Source Database', related='esg_emission_factor_id.database_id')
    company_id = fields.Many2one('res.company')
    account_id = fields.Many2one('account.account')
    activity_type_ids = fields.Many2many('esg.activity.type', related='esg_emission_factor_id.activity_type_ids')

    @api.depends('esg_emission_factor_id')
    def _compute_uom_id(self):
        for emission in self:
            if not emission._origin.id or emission._origin.id > 0:
                emission.uom_id = emission.esg_emission_factor_id.uom_id

    @api.depends('esg_emission_factor_id')
    def _compute_currency_id(self):
        for emission in self:
            if not emission._origin.id or emission._origin.id > 0:
                emission.currency_id = emission.esg_emission_factor_id.currency_id

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    oe.id AS id,
                    oe.date AS date,
                    oe.date_end as date_end,
                    oe.esg_emission_factor_id AS esg_emission_factor_id,
                    NULL AS move_id,
                    oe.name as name,
                    oe.note AS note,
                    oe.quantity as quantity,
                    ef.esg_emissions_value * oe.esg_emission_multiplicator as esg_emissions_value,
                    ef.esg_emissions_value * oe.esg_emission_multiplicator * ef.esg_uncertainty_value as esg_uncertainty_absolute_value,
                    (ef.esg_emissions_value * oe.esg_emission_multiplicator) / 1000 as esg_emissions_value_t,
                    oe.uom_id as uom_id,
                    oe.currency_id as currency_id,
                    NULL as price_subtotal,
                    NULL as partner_id,
                    oe.company_id as company_id,
                    NULL as account_id
                FROM esg_other_emission oe
                LEFT JOIN esg_emission_factor ef ON ef.id = oe.esg_emission_factor_id
                UNION ALL
                SELECT
                    -aml.id AS id,
                    aml.date AS date,
                    NULL as date_end,
                    aml.esg_emission_factor_id AS esg_emission_factor_id,
                    aml.move_id as move_id,
                    aml.name as name,
                    NULL AS note,
                    aml.quantity as quantity,
                    ef.esg_emissions_value * aml.esg_emission_multiplicator as esg_emissions_value,
                    ef.esg_emissions_value * aml.esg_emission_multiplicator * ef.esg_uncertainty_value as esg_uncertainty_absolute_value,
                    (ef.esg_emissions_value * aml.esg_emission_multiplicator) / 1000 as esg_emissions_value_t,
                    aml.product_uom_id as uom_id,
                    aml.currency_id as currency_id,
                    aml.price_subtotal as price_subtotal,
                    aml.partner_id as partner_id,
                    aml.company_id as company_id,
                    aml.account_id as account_id
                FROM account_move_line aml
                LEFT JOIN esg_emission_factor ef ON ef.id = aml.esg_emission_factor_id
                LEFT JOIN account_account aa ON aa.id = aml.account_id
                WHERE aml.quantity > 0 AND aml.parent_state = 'posted' AND aa.account_type IN {self.env['account.account'].ESG_VALID_ACCOUNT_TYPES}
            )
        """)

    def action_open_emission_form(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
        }
        if self.id > 0:
            return {
                **action,
                'res_model': 'esg.other.emission',
                'res_id': self.id,
            }
        return {
            **action,
            'res_model': 'account.move',
            'res_id': self.move_id.id,
        }

    def _update_field_value(self, field, value):
        field_description = self._fields.get(field)
        if field_description.relational:
            self.env.cache._set_field_cache(self, field_description).update({self.id: value.id or None})
        else:
            self.env.cache._set_field_cache(self, field_description).update({self.id: value})

    def write(self, vals):
        # To refactor
        other_emissions_from_report = self.filtered(lambda rec: rec.id > 0)
        account_emissions_from_report = self.filtered(lambda rec: rec.id < 0)

        other_emissions = self.env['esg.other.emission'].browse(other_emissions_from_report.ids)
        account_emissions = self.env['account.move.line'].browse(account_emissions_from_report.mapped(lambda aml: -aml.id))

        writable_fields = ['esg_emission_factor_id']
        writable_other_emissions_fields = [*writable_fields, 'date', 'date_end', 'quantity', 'note', 'uom_id', 'currency_id', 'name', 'company_id']
        writable_account_emissions_fields = writable_fields

        res = other_emissions.write({k: v for k, v in vals.items() if k in writable_other_emissions_fields}) and \
        account_emissions.write({k: v for k, v in vals.items() if k in writable_account_emissions_fields})

        readable_fields = ['esg_emission_factor_id', 'esg_emissions_value', 'esg_uncertainty_value', 'esg_uncertainty_absolute_value']
        readable_other_emissions_fields = [*readable_fields, 'date', 'date_end', 'quantity', 'note', 'uom_id', 'currency_id', 'name', 'company_id']
        readable_account_emissions_fields = readable_fields

        for other_emission_from_report, other_emission in zip(other_emissions_from_report, other_emissions):
            for field in readable_other_emissions_fields:
                other_emission_from_report._update_field_value(field, other_emission[field])

        for account_emission_from_report, account_emission in zip(account_emissions_from_report, account_emissions):
            for field in readable_account_emissions_fields:
                account_emission_from_report._update_field_value(field, account_emission[field])

        return res

    def unlink(self):
        account_emissions_from_report = self.filtered(lambda rec: rec.id < 0)
        if account_emissions_from_report:
            raise UserError(self.env._('You cannot delete journal items from here.'))  # pylint: disable=E8503

        other_emissions_from_report = self.filtered(lambda rec: rec.id > 0)
        other_emissions = self.env['esg.other.emission'].browse(other_emissions_from_report.ids)
        res = other_emissions.unlink()
        return res

    def copy(self, default=None):
        account_emissions_from_report = self.filtered(lambda rec: rec.id < 0)
        if account_emissions_from_report:
            raise UserError(self.env._('You cannot copy emissions linked to journal items.'))

        other_emissions_from_report = self.filtered(lambda rec: rec.id > 0)
        other_emissions = self.env['esg.other.emission'].browse(other_emissions_from_report.ids)
        other_emissions.copy(default)
        return True
