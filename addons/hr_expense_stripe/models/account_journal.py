from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.hr_expense_stripe.utils import make_request_stripe_proxy


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # We put the fields here instead of the company to avoid having concurrency errors when the webhook tries to update it
    stripe_currency_id = fields.Many2one(related="company_id.stripe_currency_id")
    stripe_issuing_balance = fields.Monetary(
        string="Stripe Balance Available",
        currency_field='currency_id',
        readonly=True,
    )
    stripe_issuing_balance_timestamp = fields.Integer(
        string="Timestamp of the most recent Stripe Issuing Balance update",
    )
    stripe_card_ids = fields.One2many(
        comodel_name='hr.expense.stripe.card',
        inverse_name='journal_id',
        string="Stripe Cards",
        help="Stripe cards associated with this journal. "
             "They can be used to pay for expenses, or to top up the Stripe Issuing balance.",
    )
    nb_stripe_card = fields.Integer(
        compute='_compute_nb_stripe_card',
        compute_sudo=True,
    )

    @api.constrains('bank_statements_source')
    def check_stripe_currency_existance(self):
        for journal in self:
            if not journal.company_id.stripe_currency_id and journal.bank_statements_source == 'stripe_issuing':
                raise ValidationError(_("Stripe issuing is not supported for your localization"))

    def _compute_nb_stripe_card(self):
        for journal in self:
            journal.nb_stripe_card = len(journal.stripe_card_ids)

    def __get_bank_statements_available_sources(self):
        # EXTEND account to add the "Stripe issuing" source, which only serves to setup the journal dashboard elements
        rslt = super().__get_bank_statements_available_sources()
        rslt.append(('stripe_issuing', _("Stripe Issuing")))
        return rslt

    def _fill_bank_cash_dashboard_data(self, dashboard_data):
        # EXTEND account to add specific Stripe online balance to the stripe journal
        super()._fill_bank_cash_dashboard_data(dashboard_data)
        prefetch_ids = tuple(dashboard_data.keys())
        company_stripe_journal_ids = set(self.env.companies.stripe_journal_id.ids)
        for journal_id, journal_data in dashboard_data.items():
            if journal_id in company_stripe_journal_ids:
                journal = self.browse(journal_id).with_prefetch(prefetch_ids)
                journal_data.update({
                    'stripe_issuing_activated': journal.company_id.stripe_issuing_activated,
                    'stripe_issuing_balance': journal.stripe_currency_id.format(journal.stripe_issuing_balance),
                })

    def action_open_stripe_issuing_cards(self):
        return self.stripe_card_ids._get_records_action()

    def action_open_topup_wizard(self):
        """ Open the wizard to create payments and show funding instructions"""
        self.ensure_one()
        self.env['hr.expense.stripe.topup.wizard'].check_access('create')

        if 'EU' in (self.company_id.country_id.country_group_codes or []):
            stripe_country = 'eu'
        elif self.company_id.country_id.code == 'US':
            stripe_country = 'us'
        elif self.company_id.country_id.code == 'GB':
            stripe_country = 'gb'
        else:
            raise UserError(_("Stripe Issuing is not available in your country."))

        if stripe_country == 'us':
            usd = self.env.ref('base.USD')
            if not usd.active:
                usd.active = True
            wizard = self.env['hr.expense.stripe.topup.wizard'].create([{
                'company_id': self.company_id.id,
                'currency_id': usd.id,
                'is_live_mode': self.company_id._get_stripe_mode() == 'live',
            }])
        else:
            company_sudo = self.company_id.sudo()
            payload = {
                'account': company_sudo.stripe_id,
                'bank_transfer': {'type': f'{stripe_country}_bank_transfer'},
                'currency': self.company_id.stripe_currency_id.name,
                'funding_type': 'bank_transfer',
            }
            response = make_request_stripe_proxy(company_sudo, route='funding_instructions', payload=payload, method='POST')
            wizard = self.env['hr.expense.stripe.topup.wizard'].with_company(self.company_id)._create_from_funding_instructions(response)

        return {
            'name': _("Top-up"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'hr.expense.stripe.topup.wizard',
            'res_id': wizard.id,
            'target': 'new',
        }
