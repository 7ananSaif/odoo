
from odoo import api, fields, models
from odoo.tools.translate import LazyTranslate

from odoo.addons.account_reports.models.account_return import LIMIT_CHECK_ENTRIES

_lt = LazyTranslate(__name__)


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    is_intrastat_return_type = fields.Boolean(string="Is an Intrastat Return Type", compute="_compute_is_intrastat_return_type")

    @api.depends('report_id')
    def _compute_is_intrastat_return_type(self):
        generic_intrastat_report = self.env.ref('account_intrastat.intrastat_report')
        generic_service_intrastat_report = self.env.ref('account_intrastat.intrastat_report_services')
        for record in self:
            report = record.report_id
            record.is_intrastat_return_type = (report and (
                generic_intrastat_report in (report, report.root_report_id) or
                generic_service_intrastat_report in (report, report.root_report_id)
            ))

    def _compute_states_workflow(self):
        super()._compute_states_workflow()
        for return_type in self:
            if return_type.is_intrastat_return_type:
                return_type.states_workflow = 'generic_state_review_submit'


class AccountReturn(models.Model):
    _inherit = 'account.return'

    is_intrastat_return = fields.Boolean(related="type_id.is_intrastat_return_type")

    def _run_checks(self, check_codes_to_ignore):
        checks = super()._run_checks(check_codes_to_ignore)
        if self.is_intrastat_return:
            checks += self._check_suite_common_intrastat_goods(check_codes_to_ignore)
        return checks

    def _check_suite_common_intrastat_goods(self, check_codes_to_ignore):
        checks = []

        self._generic_vies_vat_check(check_codes_to_ignore, checks)

        if 'check_intrastat_only_b2b_customer' not in check_codes_to_ignore:
            report_options = self._get_closing_report_options()
            options_domain = self.type_id.report_id._get_options_domain(report_options, 'strict_range')

            non_business_partner_ids = self.env['res.partner'].browse(
                group_result[0].id
                for group_result in self.env['account.move.line'].sudo()._read_group(
                    domain=[
                        *options_domain,
                        ('partner_id.vat', 'in', ('/', False)),
                    ],
                    groupby=['partner_id'],
                    limit=LIMIT_CHECK_ENTRIES,
                )
            )

            non_business_partners_count = len(non_business_partner_ids)
            checks.append({
                'code': 'check_intrastat_only_b2b_customer',
                'name': _lt('Only business customers'),
                'message': _lt('Exclude sales made to private individuals from the listing.'),
                'records_count': non_business_partners_count,
                'records_model': self.env['ir.model']._get('res.partner').id,
                'action': non_business_partner_ids._get_records_action() if non_business_partner_ids else False,
                'result': 'reviewed' if not non_business_partner_ids else 'anomaly',
            })

        if 'check_intrastat_only_intra_eu' not in check_codes_to_ignore:
            checks.append({
                'code': 'check_intrastat_only_intra_eu',
                'name': _lt('Only intra-EU transactions'),
                'message': _lt('Exclude any domestic or extra-EU sales from the Intrastat report.'),
                'result': 'reviewed',
            })

        if 'check_intrastat_vat_exclusive' not in check_codes_to_ignore:
            checks.append({
                'code': 'check_intrastat_vat_exclusive',
                'name': _lt('VAT exclusive'),
                'message': _lt('The value of goods should be VAT exclusive.'),
                'result': 'reviewed',
            })

        if 'check_intrastat_only_goods' not in check_codes_to_ignore:
            checks.append({
                'code': 'check_intrastat_only_goods',
                'name': _lt('Only goods included'),
                'message': _lt('Exclude services from the report.'),
                'result': 'todo',
            })

        if 'check_intrastat_commodity_code' not in check_codes_to_ignore:
            checks.append({
                'code': 'check_intrastat_commodity_code',
                'name': _lt('Commodity codes configuration'),
                'message': _lt(
                    'Verify that each item has the appropriate code and description according to the CN (Combined Nomenclature) codes.'
                ),
                'result': 'todo',
            })

        if 'check_intrastat_uom' not in check_codes_to_ignore:
            checks.append({
                'code': 'check_intrastat_uom',
                'name': _lt('Unit of measure configuration'),
                'message': _lt('Verify that each good is assigned the right unit of measure.'),
                'result': 'todo',
            })

        if 'check_intrastat_threshold' not in check_codes_to_ignore:
            checks.append({
                'code': 'check_intrastat_threshold',
                'name': _lt('Intrastat Thresholds'),
                'message': _lt(
                    'Intrastat thresholds may change annually. Verify that your transactions exceed the threshold for reporting.'
                ),
                'result': 'todo',
            })

        return checks
