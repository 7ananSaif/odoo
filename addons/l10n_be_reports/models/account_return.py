from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    def _get_start_date_elements(self, main_company):
        return super()._get_start_date_elements(main_company)

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None):
        super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)

        if country_code != 'BE':
            return

        # BE Intracom return generation
        ec_sales_return_type = self.env.ref('l10n_be_reports.be_ec_sales_list_return_type')
        months_offset = ec_sales_return_type._get_periodicity_months_delay(main_company)
        company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, ec_sales_return_type.report_id)

        tags_info = self.env['l10n_be.ec.sales.report.handler']._get_tax_tags_for_belgian_sales_report()
        ec_sales_tag_ids = set(tags_info['goods'] + tags_info['triangular'] + tags_info['services'])

        today = fields.Date.context_today(self)

        # Generate BE ec sales returns of the last 3 months and the next month if at least a move line exists in the corresponding period
        periods = [today - relativedelta(months=months_offset * i) for i in range(-1, 4)]

        # Map each period to whether it has move lines
        periods_has_move_lines_map = {
            period_bounds: bool(self.env['account.move.line'].search(
                domain=Domain([
                    ('tax_tag_ids', 'in', ec_sales_tag_ids),
                    ('company_id', 'in', company_ids.ids),
                    ('date', '>=', period_bounds[0]),
                    ('date', '<=', period_bounds[1]),
                    ('parent_state', '=', 'posted'),
                ]),
                limit=1,
            ))
            for period_bounds in (
                ec_sales_return_type._get_period_boundaries(main_company, period)
                for period in periods
            )
        }

        for (start, end), has_lines in periods_has_move_lines_map.items():
            if has_lines:
                ec_sales_return_type._try_create_return_for_period(start, main_company, tax_unit)


class AccountReturn(models.Model):
    _inherit = 'account.return'

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        months_per_period = return_type._get_periodicity_months_delay(company)
        if return_type.with_company(company).deadline_days_delay:
            pass

        elif return_type_external_id in ('l10n_be_reports.be_vat_return_type', 'l10n_be_reports.be_ec_sales_list_return_type') and months_per_period in (1, 3):
            # https://finances.belgium.be/fr/entreprises/tva/calendrier-tva#q1
            return date_to + relativedelta(days=20 if months_per_period == 1 else 25)

        elif return_type_external_id == 'l10n_be_reports.be_vat_listing_return_type':
            return date_to + relativedelta(months=3)

        elif return_type_external_id == 'l10n_be_reports.be_isoc_prepayment_return_type':
            return date_to + relativedelta(days=-9 if date_to.month == 12 else 10)

        elif return_type_external_id == 'account_reports.annual_corporate_tax_return_type' and company.account_fiscal_country_id.code == 'BE':
            return date_to + relativedelta(months=7)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

    def _get_pay_wizard(self):
        if self.type_external_id == 'l10n_be_reports.be_vat_return_type':
            # If the amount is to be recovered, we don't want to open the wizard and just continue to the next state
            if self.amount_to_pay_currency_id.compare_amounts(self.total_amount_to_pay, 0) == -1:
                return

            vat_pay_wizard = self.env['l10n_be_reports.vat.pay.wizard'].create([{
                'company_id': self.company_id.id,
                'partner_bank_id': self.type_id.payment_partner_bank_id.id,
                'currency_id': self.amount_to_pay_currency_id.id,
                'return_id': self.id,
            }])

            return {
                'type': 'ir.actions.act_window',
                'name': _("VAT Payment"),
                'res_model': 'l10n_be_reports.vat.pay.wizard',
                'res_id': vat_pay_wizard.id,
                'views': [(False, 'form')],
                'target': 'new',
            }
        elif self.type_external_id == 'l10n_be_reports.be_isoc_prepayment_return_type':
            account_return = self.env['account.return'].search([
                ('type_id', '=', self.type_id.id),
                ('date_to', '<', self.date_from),
                ('company_id', '=', self.company_id.id),
                (self.type_id.states_workflow, '=', 'paid'),
            ], order="date_to desc", limit=1)

            create_vals = {
                'company_id': self.company_id.id,
                'partner_bank_id': self.type_id.payment_partner_bank_id.id,
                'currency_id': self.amount_to_pay_currency_id.id,
                'return_id': self.id,
            }

            if not self.amount_to_pay_currency_id.is_zero(self.total_amount_to_pay):
                create_vals['amount_to_pay'] = self.total_amount_to_pay
                # Reset amount to pay as we only save it for opening the wizard
                # We need to reset it so the compute can work correctly
                self.total_amount_to_pay = 0
            elif account_return:
                create_vals['amount_to_pay'] = account_return.total_amount_to_pay

            wizard = self.env['l10n_be_reports.isoc.prepayment.pay.wizard'].create(create_vals)

            return {
                'type': 'ir.actions.act_window',
                'name': self.type_id.name,
                'res_id': wizard.id,
                'res_model': 'l10n_be_reports.isoc.prepayment.pay.wizard',
                'views': [(False, 'form')],
                'target': 'new',
                'context': {
                    'dialog_size': 'large',
                }
            }

        return super()._get_pay_wizard()

    def _run_checks(self, check_codes_to_ignore):
        checks = super()._run_checks(check_codes_to_ignore)

        if self.type_external_id == 'l10n_be_reports.be_vat_listing_return_type':
            checks += self._check_suite_be_partner_vat_listing(check_codes_to_ignore)

        return checks

    def _check_suite_be_partner_vat_listing(self, check_codes_to_ignore):
        checks = []
        if 'sales_threshold' not in check_codes_to_ignore:
            # The report always ensures that though SQL, so the test can never fail; we still add it to reassure the user
            checks.append({
                'name': _lt("Sales above 250€"),
                'message': _lt("Only include customers with total annual taxable sales exceeding 250€ (excluding VAT) or a credit note."),
                'code': 'sales_threshold',
                'result': 'reviewed',
            })

        if 'customer_without_country' not in check_codes_to_ignore:
            domain = [
                ('company_id', 'in', self.company_ids.ids),
                ('date', '<=', fields.Date.to_string(self.date_to)),
                ('date', '>=', fields.Date.to_string(self.date_from)),
                ('state', '=', 'posted'),
                ('partner_id.country_id', '=', False),
                ('move_type', 'in', self.env['account.move'].get_sale_types()),
            ]
            no_country_moves_count = self.env['account.move'].search_count(domain, limit=21)
            action = {
                'type': 'ir.actions.act_window',
                'name': _("Invoices Without Country"),
                'view_mode': 'list',
                'res_model': 'account.move',
                'domain': domain,
                'views': [[False, 'list'], [False, 'form']],
            }
            check_vals = {
                'name': _lt("No customer without country"),
                'message': _lt("Review invoices having a customer with no country specified."),
                'code': 'customer_without_country',
                'records_count': no_country_moves_count,
                'records_model': self.env['ir.model']._get('account.move').id,
                'result': 'anomaly' if no_country_moves_count else 'reviewed',
                'action': action if no_country_moves_count else False,
            }

            checks.append(check_vals)

        return checks

    def action_validate(self, bypass_failing_tests=False):
        # OVERRIDE
        if self.type_external_id == 'l10n_be_reports.be_vat_return_type':
            self._review_checks(bypass_failing_tests)
            new_wizard = self.env['l10n_be_reports.vat.return.lock.wizard'].create([{'return_id': self.id}])
            return {
                'type': 'ir.actions.act_window',
                'name': _('Lock'),
                'view_mode': 'form',
                'res_model': 'l10n_be_reports.vat.return.lock.wizard',
                'target': 'new',
                'res_id': new_wizard.id,
                'views': [[self.env.ref('l10n_be_reports.vat_return_lock_wizard_form').id, 'form']],
                'context': {
                    'dialog_size': 'medium',
                },
            }

        return super().action_validate(bypass_failing_tests)

    def action_submit(self):
        # OVERRIDE
        self._check_all_branches_allowed()
        if self.type_external_id == 'l10n_be_reports.be_vat_return_type':
            return self.env['l10n_be_reports.vat.return.submission.wizard']._open_submission_wizard(self)

        if self.type_external_id == 'account_reports.annual_corporate_tax_return_type' and self.company_id.account_fiscal_country_id.code == 'BE':
            return self.env['l10n_be_reports.annual.corporate.tax.submission.wizard']._open_submission_wizard(
                self,
                instructions=_("""
                    <p>
                        Once your accounting year is closed, it's time to think about corporate income tax (ISOC).<br/>
                        Here's the key info in 4 simple steps:
                    </p>
                    <ol>
                        <li>Year-end = the countdown starts. You have 7 months to file your ISOC return via <a href="https://finances.belgium.be/fr/E-services/biztax" target="new">Biztax</a>.</li>
                        <li>Your profit is taxed at 20% or 25%, depending on your company's status and the amount of profit.</li>
                        <li>Any advance tax payments (prepayments) you've made will be automatically deducted from the total tax due.</li>
                        <li>Overpaid? You get a refund. Underpaid? You'll need to pay the balance (and possibly a surcharge).</li>
                    </ol>
                """)
            )

        if self.type_external_id == 'l10n_be_reports.be_vat_listing_return_type':
            return self.env['l10n_be_reports.vat.listing.submission.wizard']._open_submission_wizard(self)

        if self.type_external_id == 'l10n_be_reports.be_ec_sales_list_return_type':
            return self.env['l10n_be_reports.ec.sales.list.submission.wizard']._open_submission_wizard(self)

        return super().action_submit()

    def _generate_locking_attachments(self, options):
        super()._generate_locking_attachments(options)
        if self.type_external_id == 'l10n_be_reports.be_vat_listing_return_type':
            self._add_attachment(self.type_id.report_id.dispatch_report_action(options, 'partner_vat_listing_export_to_xml'))
        elif self.type_external_id == 'l10n_be_reports.be_ec_sales_list_return_type':
            self._add_attachment(self.type_id.report_id.dispatch_report_action(options, 'export_to_xml_sales_report'))

    def l10n_be_reset_2_sates_common(self):
        return self.action_reset_2_states()

    def l10n_be_reset_tax_prepayment(self):
        self.ensure_one()

        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_("Only an Accounting Administrator can reset a tax return"))

        if self.state == 'paid':
            self._reset_checks_for_states([self.state, 'new'])
            self.state = 'new'

        self.is_completed = False

        return True
