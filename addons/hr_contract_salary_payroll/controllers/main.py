# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo.addons.hr_contract_salary.controllers import main
from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools.float_utils import float_compare


class HrContractSalary(main.HrContractSalary):

    def _can_submit_offer(self, values):
        return not values.get('is_simulation_offer', False) and super()._can_submit_offer(values)

    def _check_link_access(self, offer, **kw):
        if not request.env.user.has_group('hr.group_hr_manager') and offer.is_simulation_offer:
            if not self._check_access_token(offer, kw.get('token')):
                return False, _('This link is invalid. Please contact the HR Responsible to get a new one...')
        return super()._check_link_access(offer, **kw)

    def _get_default_template_values(self, version, offer):
        values = super()._get_default_template_values(version, offer)
        values.update({
            'is_simulation_offer': offer.is_simulation_offer
        })
        return values

    def _get_new_version_values(self, version_vals, employee, benefits, offer):
        new_version_vals = super()._get_new_version_values(version_vals, employee, benefits, offer)
        new_version_vals['work_entry_source'] = version_vals.get('work_entry_source')
        new_version_vals['standard_calendar_id'] = version_vals.get('standard_calendar_id')
        if version_vals.get('wage_type') == 'hourly':
            new_version_vals['hourly_wage'] = version_vals.get('hourly_wage')
        return new_version_vals

    def _get_personal_infos(self, version, offer):
        if not offer.is_simulation_offer:
            return super()._get_personal_infos(version, offer)

        mapped_personal_infos, new_dropdown_options, new_initial_values = super()._get_personal_infos(version, offer)
        new_mapped_personal_infos = defaultdict(lambda: request.env['hr.contract.salary.personal.info'])

        for key, personal_infos in mapped_personal_infos.items():
            for personal_info in personal_infos:
                if personal_info.impacts_net_salary:
                    new_mapped_personal_infos[key] |= personal_info
                else:
                    new_initial_values.pop(personal_info.field, None)
                    new_initial_values.pop(personal_info.field + '_filename', None)
                    new_dropdown_options.pop(personal_info.field, None)

        return new_mapped_personal_infos, new_dropdown_options, new_initial_values

    def _get_payslip_line_values(self, payslip, codes):
        return payslip._get_line_values(codes)

    def _get_compute_results(self, new_version):
        schedule_pay_label = dict(request.env['hr.version']._fields['schedule_pay']._description_selection(request.env))

        def _get_period_name(category_id, version):
            if category_id == request.env.ref("hr_contract_salary.hr_contract_salary_resume_category_monthly_salary"):
                # ISSUE:
                # The salary configurator was originally designed with the assumption that
                # the pay schedule is always "monthly". When we changed the schedule pay
                # selection labels (e.g., "monthly" -> "month"), the configurator started
                # displaying "month Salary" instead of the expected "Monthly Salary"
                # and "Gross (Incl. Comm)" instead of "Gross".
                # FIX:
                # As a temporary workaround, we hardcode "Monthly Salary" when
                # version.schedule_pay == 'monthly' because the configurator is not adapted for other pay schedule than monthly.
                # For all other schedule_pay values, we keep using the schedule_pay_label mapping,
                # until the configurator is properly adapted to support non-monthly schedules.
                if version.schedule_pay == 'monthly':
                    return "Monthly Salary"
                period_name = schedule_pay_label.get(version.schedule_pay, "Monthly")
                return f"{period_name} Salary"
            return category_id.name

        result = super()._get_compute_results(new_version)

        # generate a payslip corresponding to only this version
        payslip = new_version._generate_salary_simulation_payslip()

        result['payslip_lines'] = [(
            line.name,
            f'{line.total:.2f}',
            line.code,
            'total' if line.code in ['BASIC', 'SALARY', 'GROSS', 'NET', 'GROSSIP'] else float_compare(line.total, 0, precision_digits=2),
            new_version.company_id.currency_id.position,
            new_version.company_id.currency_id.symbol
        ) for line in payslip.line_ids.filtered(lambda l: l.appears_on_payslip)]
        # Allowed company ids might not be filled or request.env.user.company_ids might be wrong
        # since we are in route context, force the company to make sure we load everything
        resume_lines = request.env['hr.contract.salary.resume'].sudo().with_company(new_version.company_id).search([
            '|',
            ('structure_type_id', '=', False),
            ('structure_type_id', '=', new_version.structure_type_id.id),
            ('value_type', 'in', ['payslip', 'monthly_total'])])
        monthly_total = 0
        monthly_total_lines = resume_lines.filtered(lambda l: l.value_type == 'monthly_total')

        # new categories could be introduced at this step
        # recreate resume_categories
        resume_categories = request.env['hr.contract.salary.resume'].sudo().with_company(new_version.company_id).search([
            '|', '&', '|',
                    ('structure_type_id', '=', False),
                    ('structure_type_id', '=', new_version.structure_type_id.id),
                ('value_type', 'in', ['fixed', 'version', 'monthly_total', 'sum']),
            ('id', 'in', resume_lines.ids)]).category_id
        result['resume_categories'] = [_get_period_name(c, new_version) for c in sorted(resume_categories, key=lambda x: x.sequence)]

        all_codes = (resume_lines - monthly_total_lines).mapped('code')
        line_values = self._get_payslip_line_values(payslip, all_codes) if all_codes else False

        for resume_line in resume_lines - monthly_total_lines:
            value = round(line_values[resume_line.code][payslip.id]['total'], 2)
            resume_explanation = False
            if resume_line.code == 'GROSS' and new_version.wage_type == 'hourly':
                hours = payslip.worked_days_line_ids.number_of_hours
                resume_explanation = self.env._('This is the gross calculated for the current month with a total of %s hours.', hours)
            result['resume_lines_mapped'][_get_period_name(resume_line.category_id, new_version)][resume_line.code] = (resume_line.name, value, new_version.company_id.currency_id.symbol, resume_explanation, new_version.company_id.currency_id.position, resume_line.uom)
            if resume_line.impacts_monthly_total:
                monthly_total += value / 12.0 if resume_line.category_id.periodicity == 'yearly' else value

        for resume_line in monthly_total_lines:
            super_line = result['resume_lines_mapped'][_get_period_name(resume_line.category_id, new_version)][resume_line.code]
            line_name = super_line[0]
            if resume_line.category_id == request.env.ref("hr_contract_salary.hr_contract_salary_resume_category_total"):
                period_name = schedule_pay_label.get(new_version.schedule_pay, "Monthly")
                line_name = f"{period_name} Equivalent"
            new_value = (line_name, round(super_line[1] + float(monthly_total), 2), super_line[2], False, new_version.company_id.currency_id.position, resume_line.uom)
            result['resume_lines_mapped'][_get_period_name(resume_line.category_id, new_version)][resume_line.code] = new_value

        return result

    def _update_version_payroll_properties(self, version, benefits):
        version_benefits = request.env['hr.contract.salary.benefit'].sudo().search([
            ('structure_type_id', '=', version.structure_type_id.id),
            ('source', '=', 'rule')])
        variants = [
                '',
                "_manual",
                "_radio",
                "_slider",
        ]
        for benefit in version_benefits:
            fields = ['%s%s' % (benefit.field, k) for k in variants]
            value = next((benefits[field] for field in fields if field in benefits), None) or 0.0
            version._set_property_input_value(benefit.salary_rule_id.code, float(value))

    def create_new_version(self, version_vals, offer_id, benefits, no_write=False, **kw):
        new_version, version_diff = super().create_new_version(version_vals, offer_id, benefits, no_write=no_write, **kw)
        benefits_values = benefits['version']
        request.env.flush_all()
        with request.env.cr.savepoint(flush=False) as sp:
            offer = request.env['hr.contract.salary.offer'].sudo().browse(offer_id)
            version = offer._get_version()
            new_version.write({
                'payroll_properties': dict(version.payroll_properties),
            })
            request.env.flush_all()
            sp.rollback()
        self._update_version_payroll_properties(new_version, benefits_values)
        return new_version, version_diff

    @http.route()
    def submit(self, offer_id=None, benefits=None, **kw):
        offer = request.env['hr.contract.salary.offer'].sudo().browse(offer_id)
        if offer.is_simulation_offer:
            raise UserError(self.env._('This offer is a simulation. You cannot submit this salary package.'))
        return super().submit(offer_id, benefits, **kw)
