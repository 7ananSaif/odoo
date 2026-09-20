from odoo import models, fields, api


class L10nBeHolidayAttestWizard(models.TransientModel):
    _name = 'l10n.be.holiday.attest.wizard'
    _description = 'Holiday Attest Wizard'

    months_count = fields.Float(string='Number of Months', required=True)
    occupation_rate = fields.Float(string='Occupation Rate (%)', required=True)
    amount = fields.Monetary(string='Amount', required=True)
    currency_id = fields.Many2one(
        'res.currency',
        required=True,
        compute='_compute_currency_id',
        precompute=True,
        store=True
    )

    employee_id = fields.Many2one('hr.employee', required=True)
    year = fields.Integer(required=True)

    @api.depends('employee_id')
    def _compute_currency_id(self):
        for wizard in self:
            wizard.currency_id = wizard.employee_id.currency_id.id

    def action_create_attest_line(self):
        val_list = []
        for wizard in self:
            val_list.append({
                'months_count': wizard.months_count,
                'occupation_rate': wizard.occupation_rate,
                'amount': wizard.amount,
                'employee_id': wizard.employee_id.id,
                'year': wizard.year,
            })
        self.env['l10n.be.double.pay.recovery.line'].create(val_list)
        return {'type': 'ir.actions.act_window_close'}
