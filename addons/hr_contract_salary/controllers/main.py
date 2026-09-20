# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib

from collections import defaultdict, OrderedDict
from odoo import fields, http, models, _, Command

from odoo.addons.sign.controllers.main import Sign
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools import consteq
from odoo.tools.image import image_data_uri
from werkzeug.exceptions import NotFound
from werkzeug.wsgi import get_current_url
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta


class SignContract(Sign):

    @http.route()
    def sign(self, sign_request_id, token, sms_token=False, signature=None, **kwargs):
        result = super().sign(sign_request_id, token, sms_token=sms_token, signature=signature, **kwargs)
        if result.get('success'):
            request_item = request.env['sign.request.item'].sudo().search([('access_token', '=', token)])
            version = request.env['hr.version'].sudo().search([
                ('sign_request_ids', 'in', request_item.sign_request_id.ids),
                '|',
                    ('active', '=', True),
                    ('active', '=', False)
            ])
            offer = request.env['hr.contract.salary.offer'].sudo().search([
                ('sign_request_ids', 'in', request_item.sign_request_id.ids)])
            if offer.state in ['expired', 'refused']:
                raise UserError(_('This offer is outdated, please request an updated link...'))
            request_template_id = request_item.sign_request_id.template_id.id
            # Only if the signed document is the document to sign from the salary package
            version_documents = [
                version.sign_template_id.id,
                version.contract_update_template_id.id,
            ]
            if version and request_template_id in version_documents:
                self._update_version_on_signature(request_item, version, offer)
                if request_item.sign_request_id.nb_closed == 1:
                    return dict(result, url='/salary_package/thank_you/' + str(offer.id))
        return result

    def _update_version_on_signature(self, request_item, version, offer):
        wage_to_apply = version._get_wage_to_apply()
        # Only the applicant/employee has signed
        if request_item.sign_request_id.nb_closed == 1:
            version.hash_token = False
            if version.applicant_id:
                version.applicant_id.employee_id = version.employee_id
            version.wage_on_signature = wage_to_apply

            if not request_item.sign_request_id.nb_wait:
                if version.employee_id:
                    version.employee_id.active = True
                    if version.applicant_id:
                        version.applicant_id._move_to_hired_stage()
                    if version.employee_id.work_contact_id:
                        version.employee_id.work_contact_id.active = True
                self._create_activity_benefit(version, ('running', 'countersigned'))
                self._send_benefit_sign_request(version)
                offer.state = "full_signed"

            else:
                self._create_activity_benefit(version, ('running'))
                offer.state = "half_signed"

        # All signers have signed
        if request_item.sign_request_id.nb_wait == 0:
            current_employee_version = version.employee_id.version_id
            must_archive_current_version = version.applicant_id or False
            # If you are an employee with an existing version already, close the existing version
            if not version.applicant_id and current_employee_version.contract_date_start:
                current_employee_version.contract_date_end = (
                    version.contract_date_start - timedelta(days=1)
                )
            if current_employee_version.date_version >= version.date_version:
                # then remplace the current version with the new one signed. We must 'fake' the date_version in order
                # to be able to unarchive the new version without triggering the constraint if the two dates are equal
                current_employee_version.date_version = version.date_version - timedelta(days=1)
                must_archive_current_version = True
            request.env.flush_all()
            version.write({'active': True})
            if must_archive_current_version:
                current_employee_version.write({'active': False})
            if version.employee_id:
                version.employee_id.active = True
                if version.applicant_id:
                    version.applicant_id._move_to_hired_stage()
            if version.employee_id.work_contact_id:
                version.employee_id.work_contact_id.active = True
            self._create_activity_benefit(version, ('countersigned'))
            self._send_benefit_sign_request(version)
            offer.state = "full_signed"

    def _create_activity_benefit(self, version, contract_states):
        benefits = request.env['hr.contract.salary.benefit'].sudo().search([
            ('structure_type_id', '=', version.structure_type_id.id),
            ('activity_type_id', '!=', False),
            ('activity_creation', 'in', contract_states)])
        for benefit in benefits:
            field = benefit.field
            value = version[field] if benefit.source == 'field' else version._get_property_input_value(benefit.salary_rule_id.code)
            origin_value = version.origin_version_id[field] if benefit.source == 'field' else version.origin_version_id._get_property_input_value(benefit.salary_rule_id.code)
            if (benefit.activity_creation_type == "onchange" and value != origin_value) or \
                    benefit.activity_creation_type == "always" and value:
                version.activity_schedule(
                    activity_type_id=benefit.activity_type_id.id,
                    note="%s: %s" % (benefit.name or benefit.field, value),
                    user_id=benefit.activity_responsible_id.id)

    def _send_benefit_sign_request(self, version):
        benefits = request.env['hr.contract.salary.benefit'].sudo().search([
            ('structure_type_id', '=', version.structure_type_id.id),
            ('sign_template_id', '!=', False)])

        # ask the contract responsible to create sign requests
        SignRequestSudo = request.env['sign.request'].with_user(version.hr_responsible_id).sudo()

        sent_templates = request.env['sign.template']
        for benefit in benefits:
            field = benefit.field
            value = version[field] if benefit.source == 'field' else version._get_property_input_value(benefit.salary_rule_id.code)
            origin_value = version.origin_version_id[field] if benefit.source == 'field' else version.origin_version_id._get_property_input_value(benefit.salary_rule_id.code)
            sign_template = benefit.sign_template_id
            if sign_template in sent_templates:
                continue
            if (benefit.activity_creation_type == "onchange" and value != origin_value) or \
                    benefit.activity_creation_type == "always" and value:

                sent_templates |= sign_template
                request_items = []
                template_roles = sign_template.sign_item_ids.responsible_id

                if request.env.ref('hr_sign.sign_item_role_employee_signatory') in template_roles:
                    request_items.append(Command.create({'role_id': request.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                                        'partner_id': version.employee_id.work_contact_id.id}))

                if request.env.ref('hr_sign.sign_item_role_job_responsible') in template_roles:
                    request_items.append(Command.create({'role_id': request.env.ref('hr_sign.sign_item_role_job_responsible').id,
                                        'partner_id': version.hr_responsible_id.partner_id.id}))

                sign_request_sudo = SignRequestSudo.create({
                    'template_id': sign_template.id,
                    'request_item_ids': request_items,
                    'reference': _('Signature Request - %s', benefit.name or version.name),
                    'subject': _('Signature Request - %s', benefit.name or version.name),
                })
                sign_request_sudo.message_subscribe(partner_ids=benefit.sign_copy_partner_id.ids)
                sign_request_sudo.toggle_favorited()

                version.sign_request_ids += sign_request_sudo

class HrContractSalary(http.Controller):

    def _get_default_template_values(self, version, offer):
        values = self._get_salary_package_values(version, offer)
        values.update({
            'redirect_to_job': False,
            # YTI PROBABLY TO REMOVE
            'applicant_id': offer.applicant_id.id,
            'employee_version_id': offer.employee_version_id.id,
            'employee_job_id': offer.employee_job_id.id,
            'department_id': offer.department_id.id,
            'job_title': offer.job_title,
            'whitelist': False,
            'part_time': False,
            'final_yearly_costs': offer.final_yearly_costs,
        })
        return values

    @http.route(['/salary_package/simulation/version/<int:version_id>'], type='http', auth="public", website=True, sitemap=False)
    def salary_package_deprecated(self, version_id=None, **kw):
        return request.render('http_routing.http_error', {
            'status_code': _('Oops'),
            'status_message': _('This offer is outdated, please request an updated link...')})

    def _can_submit_offer(self, values):
        return not values['redirect_to_job']

    def check_access_to_salary_configurator(self, request_token, offer, version):
        """
        Methods of access:
        1 - User access (inside 'group_hr_manager')
        2 - User access (the user of the offered employee, if exists)
        3 - Token
        """
        if not offer.exists() or offer.state in ['expired', 'refused']:
            return False, request.render('http_routing.http_error', {
                'status_code': self.env._('Oops'),
                'status_message': self.env._('This offer has been updated, please request an updated link..')})

        if offer.offer_end_date and offer.offer_end_date < fields.Date.today():
            error_msg = self.env._("This link is invalid. Please contact the HR Responsible to get a new one...")
            return False, request.render('http_routing.http_error', {
                'status_code': self.env._('Oops'),
                'status_message': error_msg})

        request_user = request.env.user
        if request_user.has_group('hr.group_hr_manager'):
            return True, None

        if offer.access_token and request_token and consteq(offer.access_token, request_token):
            return True, None

        offer_user = offer.employee_id.user_id
        if offer_user:
            if offer_user == request_user:
                return True, None
            else:
                version.with_user(request_user.id).with_context(
                    allowed_company_ids=request_user.company_ids.ids
                ).check_access('read')
                return True, None

        if offer.access_token:
            if not request_token:
                error_msg = self.env._('Access Denied: Missing Token')
            else:
                error_msg = self.env._('Access Denied: Invalid Token')
        else:
            raise NotFound()
        return False, request.render('http_routing.http_error', {
            'status_code': self.env._('Oops'),
            'status_message': error_msg})

    @http.route(['/salary_package/simulation/offer/<int:offer_id>'], type='http', auth="public", website=True, sitemap=False)
    def salary_package(self, offer_id=None, **kw):
        response = False

        debug = request.session.debug
        for bundle_name in ["web.assets_frontend", "web.assets_frontend_lazy"]:
            request.env["ir.qweb"]._get_asset_nodes(bundle_name, debug=debug, js=True, css=True)

        # THE REST OF THE TRANSACTION WILL BE ROLLED-BACK
        # This is just a simulation.

        request.env.flush_all()
        with request.env.cr.savepoint(flush=False) as sp:
            offer = request.env['hr.contract.salary.offer'].sudo().browse(offer_id)
            version = offer._get_version()
            has_access, error_page = self.check_access_to_salary_configurator(kw.get('token'), offer, version)
            if not has_access:
                return error_page

            if offer.applicant_id:
                version = version.with_context(is_applicant=True)

            values = self._get_default_template_values(version, offer)
            for field_name, value in kw.items():
                if field_name == 'job_id':
                    values['redirect_to_job'] = value
                if field_name == 'allow':
                    values['whitelist'] = value
                if field_name == 'part':
                    values['part_time'] = True
                # Allow simulation on url's in public offers
                if field_name == 'final_yearly_costs' and not (offer.applicant_id or offer.employee_id or offer.access_token):
                    values['final_yearly_costs'] = float(value)
            new_gross = version.sudo()._get_gross_from_employer_costs(values['final_yearly_costs'])
            version.write({
                'wage': new_gross,
                'final_yearly_costs': values['final_yearly_costs'],
            })
            refusal_reasons = request.env['hr.contract.salary.offer.refusal.reason'].search([])
            values.update({
                'need_personal_information': self._can_submit_offer(values),
                'submit': self._can_submit_offer(values),
                'default_mobile': request.env['ir.default'].sudo()._get('hr.version', 'mobile'),
                'original_link': get_current_url(request.httprequest.environ),
                'token': kw.get('token'),
                'offer_id': offer.id,
                'master_department_id': request.env['hr.department'].sudo().browse(int(values['department_id'])).master_department_id.id if values['department_id'] else False,
                'refusal_reasons': refusal_reasons,
            })

            response = request.render("hr_contract_salary.salary_package", values)
            response.flatten()
            request.env.flush_all()
            sp.rollback()
        return response

    @http.route(['/salary_package/thank_you/<int:offer_id>'], type='http', auth="public", website=True, sitemap=False)
    def salary_package_thank_you(self, offer_id=None, **kw):
        offer = request.env['hr.contract.salary.offer'].sudo().browse(offer_id)
        request.env.flush_all()
        with request.env.cr.savepoint(flush=False) as sp:
            version = offer._get_version()
            result = request.render("hr_contract_salary.salary_package_thank_you", {
                'responsible_name': version.hr_responsible_id.partner_id.name or version.job_id.user_id.partner_id.name,
                'responsible_email': version.hr_responsible_id.work_email or version.job_id.user_id.partner_id.email,
                'responsible_phone': version.hr_responsible_id.work_phone or version.job_id.user_id.partner_id.phone,
            })
            request.env.flush_all()
            sp.rollback()
        return result

    def _get_personal_infos_countries(self, version, personal_info):
        return request.env['res.country'].search([])

    def _get_personal_infos_states(self, version, personal_info):
        return request.env['res.country.state'].search([])

    def _get_personal_infos_langs(self, version, personal_info):
        return request.env['res.lang'].search([])

    def _get_personal_infos(self, version, offer):
        initial_values = {}
        dropdown_options = {}
        targets = {
            'version_personal': version,
            'employee': version.employee_id,
            'bank_account': version.employee_id.primary_bank_account_id,
        }

        # PERSONAL INFOS
        personal_infos = request.env['hr.contract.salary.personal.info'].sudo().search([
            '|',
            ('structure_type_id', '=', False),
            ('structure_type_id', '=', version.structure_type_id.id)]).sorted(lambda info: (info.info_type_id.sequence, info.sequence))
        mapped_personal_infos = defaultdict(lambda: request.env['hr.contract.salary.personal.info'])

        for personal_info in personal_infos:
            mapped_personal_infos[personal_info.info_type_id.name] |= personal_info

            target = targets[personal_info.applies_on]

            if personal_info.display_type == 'document':
                if personal_info.field in target and target[personal_info.field]:
                    if target[personal_info.field][:7] == b'JVBERi0':
                        content = "data:application/pdf;base64,%s" % (target[personal_info.field].decode())
                    else:
                        content = image_data_uri(target[personal_info.field])
                else:
                    content = False
                initial_values[personal_info.field] = content
                filename_field = personal_info.field + '_filename'
                if filename_field in version._fields:
                    initial_values[personal_info.field + '_filename'] = version[filename_field]
                elif filename_field in target:
                    initial_values[personal_info.field + '_filename'] = target[filename_field]
                else:
                    initial_values[personal_info.field + '_filename'] = personal_info.field
            else:
                initial_values[personal_info.field] = target[personal_info.field] if personal_info.field in target else ''

            if personal_info.display_type == 'dropdown':
                # Set record id instead of browse record as value
                if isinstance(initial_values[personal_info.field], models.BaseModel):
                    initial_values[personal_info.field] = initial_values[personal_info.field].id

                if personal_info.dropdown_selection == 'specific':
                    values = [(value.value, value.name) for value in personal_info.value_ids]
                elif personal_info.dropdown_selection == 'country':
                    values = [(country.id, country.name) for country in self._get_personal_infos_countries(version, personal_info)]
                elif personal_info.dropdown_selection == 'state':
                    values = [(state.id, state.name, state.country_id.id) for state in self._get_personal_infos_states(version, personal_info)]
                elif personal_info.dropdown_selection == 'lang':
                    values = [(lang.code, lang.name) for lang in self._get_personal_infos_langs(version, personal_info)]
                dropdown_options[personal_info.field] = values

        return mapped_personal_infos, dropdown_options, initial_values

    def _get_benefits(self, version_vals, offer):
        return request.env['hr.contract.salary.benefit'].sudo().search([
            ('structure_type_id', '=', version_vals.get('structure_type_id'))])

    def _get_benefits_values(self, version, offer):
        initial_values = {}
        dropdown_options = {}
        dropdown_group_options = {}

        # benefits
        benefits = self._get_benefits(version._get_values_dict(), offer)
        mapped_benefits = defaultdict(lambda: request.env['hr.contract.salary.benefit'])
        for benefit in benefits:
            mapped_benefits[benefit.benefit_type_id] |= benefit
            field = benefit.field
            initial_values[field] = version[field] if benefit.source == 'field' else version._get_property_input_value(benefit.salary_rule_id.code)

            if benefit.folded:
                fold_field = 'fold_%s' % (benefit.field)
                benefit_fold_field = benefit.fold_field or benefit.field
                initial_values[fold_field] = version[benefit_fold_field] if benefit_fold_field and benefit_fold_field in version else 0

            if benefit.display_type == 'manual':
                manual_field = '%s_manual' % (benefit.field)
                field = benefit.manual_field or benefit.field
                initial_values[manual_field] = initial_values.get(field, False) or (version[field] if field and field in version else 0)
            if benefit.display_type == 'text':
                text_field = '%s_text' % (benefit.field)
                field = benefit.manual_field or benefit.field
                initial_values[text_field] = version[field] if field and field in version else ''
            elif benefit.display_type == 'dropdown' or benefit.display_type == 'dropdown-group':
                initial_values['select_%s' % field] = version[field]

        dropdown_benefits = benefits.filtered(lambda a: a.display_type == 'dropdown')
        for dropdown_benefit in dropdown_benefits:
            dropdown_options[dropdown_benefit.field] = \
                [(value.value, value.value) for value in dropdown_benefit.value_ids.filtered(lambda v: v.display_type == 'line')]
        dropdown_group_benefits = benefits.filtered(lambda a: a.display_type == 'dropdown-group')
        for dropdown_group_benefit in dropdown_group_benefits:
            values = OrderedDict()
            values[""] = []
            current_section = ""
            for value in dropdown_group_benefit.value_ids:
                if value.display_type == 'section':
                    current_section = value.name
                    values[current_section] = []
                else:
                    values[current_section].append((value.value, value.value))
            dropdown_group_options[dropdown_group_benefit.field] = values
        benefit_types = sorted(benefits.mapped('benefit_type_id'), key=lambda x: x.sequence)
        mapped_dependent_benefits = defaultdict(lambda: '')
        mapped_mandatory_benefits = defaultdict(lambda: '')
        # When the dependent benefit is disabled, on hover over we display the information
        # regarding which (mandatory) benefits need to be selected, in order to be able to select
        # the (dependent) benefit in question. For this purpose, here we build the string for each dependent benefit.
        # The string starts with the display name of the dependent benefit and is followed by the display names
        # of the mandatory benefits, separated by semicolon.
        mapped_mandatory_benefits_names = defaultdict(lambda: '')
        for dependent_benefit in benefits:
            if not dependent_benefit.field:
                continue
            mapped_mandatory_benefits_names[dependent_benefit] = (dependent_benefit.fold_label or dependent_benefit.name) + ';'
            if dependent_benefit.folded:
                dependent_name = 'fold_%s' % (dependent_benefit.field)
            else:
                dependent_name = dependent_benefit.field + '_' + dependent_benefit.display_type
            dependent_benefit_str = dependent_name + ' '
            for mandatory_benefit in dependent_benefit.benefit_ids:
                mapped_dependent_benefits[mandatory_benefit] += dependent_benefit_str
                if mandatory_benefit.folded:
                    mandatory_name = 'fold_%s' % (mandatory_benefit.field)
                else:
                    mandatory_name = mandatory_benefit.field + '_' + mandatory_benefit.display_type
                mapped_mandatory_benefits[dependent_benefit] += mandatory_name + ' '
                mapped_mandatory_benefits_names[dependent_benefit] += (mandatory_benefit.fold_label or mandatory_benefit.name) + ';'
        return mapped_benefits, mapped_dependent_benefits, mapped_mandatory_benefits, mapped_mandatory_benefits_names, benefit_types, dropdown_options, dropdown_group_options, initial_values

    def _get_salary_package_values(self, version, offer):
        mapped_personal_infos, dropdown_options_1, initial_values_1 = self._get_personal_infos(version, offer)
        mapped_benefits, mapped_dependent_benefits, mandatory_benefits, mandatory_benefits_names, benefit_types, dropdown_options_2, dropdown_group_options, initial_values_2 = self._get_benefits_values(version, offer)
        all_initial_values = {**initial_values_1, **initial_values_2}
        all_initial_values = {key: round(value, 2) if isinstance(value, float) else value for key, value in all_initial_values.items()}
        all_dropdown_options = {**dropdown_options_1, **dropdown_options_2}
        return {
            'version': version,
            'states': request.env['res.country.state'].search([]),
            'countries': request.env['res.country'].search([]),
            'benefits': mapped_benefits,
            'dependent_benefits': mapped_dependent_benefits,
            'mandatory_benefits': mandatory_benefits,
            'mandatory_benefits_names': mandatory_benefits_names,
            'benefit_types': benefit_types,
            'mapped_personal_infos': mapped_personal_infos,
            'dropdown_options': all_dropdown_options,
            'dropdown_group_options': dropdown_group_options,
            'initial_values': all_initial_values,
        }

    def _get_new_version_values(self, version_vals, employee, benefits, offer):
        version_benefits = self._get_benefits(version_vals, offer)
        company = self.env['res.company'].browse(version_vals.get('company_id'))
        new_version_vals = {
            'active': False,
            'name': version_vals.get('name') or _("Package Simulation"),
            'job_id': offer.employee_job_id.id or version_vals.get('job_id') or employee.job_id.id,
            'department_id': offer.department_id.id or version_vals.get('department_id') or employee.department_id.id,
            'company_id': company.id,
            'currency_id': company.currency_id.id,
            'employee_id': employee.id,
            'structure_type_id': version_vals.get('structure_type_id'),
            'wage': benefits['wage'],
            'final_yearly_costs': benefits['final_yearly_costs'],
            'resource_calendar_id': version_vals.get('resource_calendar_id'),
            'contract_template_id': offer.contract_template_id.id,
            'hr_responsible_id': version_vals.get('hr_responsible_id'),
            'sign_template_id': offer.sign_template_id.id,
            'contract_update_template_id': version_vals.get('contract_update_template_id'),
            'date_version': offer.contract_start_date or fields.Date.today().replace(day=1),
            'contract_date_start': offer.contract_start_date or fields.Date.today().replace(day=1),
            'contract_date_end': offer.contract_end_date,
            'contract_type_id': version_vals.get('contract_type_id'),
            'originated_offer_id': offer.id,
            'address_id': employee.address_id.id,
            'work_location_id': employee.work_location_id.id,
        }
        if 'work_entry_source' in version_vals:
            new_version_vals['work_entry_source'] = version_vals.get('work_entry_source')

        for benefit in version_benefits:
            if not benefit.res_field_id or benefit.field not in version_vals:
                continue
            if hasattr(self.env['hr.version'], '_get_benefit_values_%s' % (benefit.field)):
                new_version_vals.update(getattr(self.env['hr.version'], '_get_benefit_values_%s' % (benefit.field))(version_vals, benefits))
                continue
            if benefit.folded:
                new_version_vals[benefit.fold_field or benefit.field] = benefits['fold_%s' % (benefit.field)]
            if benefit.display_type == 'dropdown':
                new_version_vals[benefit.field] = benefits[benefit.field]
            if benefit.display_type in ['manual', 'text']:
                new_version_vals[benefit.manual_field or benefit.field] = benefits['%s_%s' % (benefit.field, 'manual' if benefit.display_type == 'manual' else 'text')]
            else:
                new_version_vals[benefit.field] = benefits[benefit.field]
        for field in offer._fields:
            if field.startswith('x_') and field not in new_version_vals and field in version_vals:
                new_version_vals[field] = offer[field]
        return new_version_vals

    def _update_personal_info(self, employee, version, personal_infos_values, no_name_write=False):
        def resolve_value(field_name, values):
            targets = {
                'version_personal': request.env['hr.version'],
                'employee': request.env['hr.employee'],
                'bank_account': request.env['res.partner.bank'],
            }
            field_value = values[field_name]

            target = targets[personal_info.applies_on]
            if field_name in target and target._fields[field_name].relational:
                field_value = int(field_value) if field_value else False
            return field_value

        def _is_valid_date(date):
            return fields.Date.from_string(date) >= fields.Date.from_string('1900-01-01')

        personal_infos = request.env['hr.contract.salary.personal.info'].sudo().search([
            '|', ('structure_type_id', '=', False), ('structure_type_id', '=', version.structure_type_id.id)])

        version_infos = personal_infos_values['version_personal']
        employee_infos = personal_infos_values['employee']
        bank_account_infos = personal_infos_values['bank_account']

        for key in ['employee_job_id', 'department_id']:
            try:
                employee_infos[key] = int(employee_infos[key])
            except (ValueError, TypeError):
                employee_infos[key] = None
        job = request.env['hr.job'].sudo().browse(employee_infos['employee_job_id'])
        if not employee_infos['job_title']:
            employee_infos['job_title'] = job.name

        employee_vals = {}
        version_vals = {}
        work_contact_vals = {}
        bank_account_vals = {}
        attachment_create_vals = []

        if employee_infos.get('birthday') and not _is_valid_date(employee_infos['birthday']):
            employee_infos['birthday'] = ''

        for personal_info in personal_infos:
            field_name = personal_info.field

            if personal_info.display_type == 'document' and not employee_infos.get(field_name):
                continue

            if field_name in employee_infos and personal_info.applies_on == 'employee':
                employee_vals[field_name] = resolve_value(field_name, employee_infos)
            elif field_name in version_infos and personal_info.applies_on == 'version_personal':
                version_vals[field_name] = resolve_value(field_name, version_infos)
            elif field_name in bank_account_infos and personal_info.applies_on == 'bank_account':
                bank_account_vals[field_name] = resolve_value(field_name, bank_account_infos)

        work_contact_vals['name'] = employee_vals.get('name', '')
        work_contact_vals['email'] = employee_vals.get('private_email', '')

        # Update personal info on the private address
        if employee.work_contact_id:
            if no_name_write or employee.user_id.name:
                del work_contact_vals['name']
            partner = employee.work_contact_id
            # We shouldn't modify the partner email like this
            if employee.work_contact_id.email:
                work_contact_vals.pop('email', None)
            partner.write(work_contact_vals)
        else:
            work_contact_vals['active'] = False
            partner = request.env['res.partner'].sudo().with_context(lang=None, tracking_disable=True).create(work_contact_vals)

        # Update personal info on the employee
        if bank_account_vals:
            bank_account_vals['partner_id'] = partner.id
            existing_bank_account = request.env['res.partner.bank'].sudo().search([
                ('partner_id', '=', partner.id),
                ('acc_number', '=', bank_account_vals['acc_number'])], limit=1)
            if existing_bank_account:
                bank_account = existing_bank_account
                if bank_account_vals.get('acc_holder_name'):
                    bank_account.acc_holder_name = bank_account_vals['acc_holder_name']
            else:
                bank_account = request.env['res.partner.bank'].sudo().create(bank_account_vals)

            employee_vals['bank_account_ids'] = [Command.link(bank_account.id)]

        employee_vals['work_contact_id'] = partner.id

        if job.address_id:
            employee_vals['address_id'] = job.address_id.id

        if not no_name_write:
            employee_vals['name'] = employee_infos.get('name', '')
        employee.with_context(tracking_disable=True).write(employee_vals)
        version.with_context(tracking_disable=True).write(version_vals)
        if attachment_create_vals:
            request.env['ir.attachment'].sudo().create(attachment_create_vals)

    def create_new_version(self, version_vals, offer_id, benefits, no_write=False, **kw):
        # Generate a new version with the current modifications
        version_diff = []
        benefits_values = benefits['version']
        personal_infos = {
            'version_personal': benefits['version_personal'],
            'employee': benefits['employee'],
            'address': benefits['address'],
            'bank_account': benefits['bank_account'],
        }
        offer = request.env['hr.contract.salary.offer'].sudo().browse(offer_id).exists()
        applicant = offer.applicant_id
        employee = kw.get('employee') or applicant.employee_id or offer.employee_id
        if not employee and applicant:
            existing_version = request.env['hr.version'].sudo().search([
                ('applicant_id', '=', applicant.id),
                ('employee_id', '!=', False),
                '|',
                    ('active', '=', True),
                    ('active', '=', False)
            ], limit=1)
            employee = existing_version.employee_id
        if not employee:
            company = self.env['res.company'].browse(version_vals.get('company_id'))
            employee_vals = {
                'name': applicant.partner_name if applicant else 'Simulation Employee',
                'active': False,
                'company_id': company.id,
                'lang': company.partner_id.lang,
                'resource_calendar_id': version_vals.get('resource_calendar_id'),
            }
            if 'current_applicant_skill_ids' in offer.applicant_id:
                employee_vals['employee_skill_ids'] = [
                    Command.create({
                        'skill_id': skill.skill_id.id,
                        'skill_type_id': skill.skill_type_id.id,
                        'skill_level_id': skill.skill_level_id.id
                    })
                    for skill in offer.applicant_id.current_applicant_skill_ids
                ]
            employee = request.env['hr.employee'].sudo().with_context(
                tracking_disable=True,
                salary_simulation=not no_write,
            ).create(employee_vals)

        # get differences for personnal information
        if no_write:
            employee_fields = request.env['hr.employee']._fields
            for section in personal_infos:
                for field in personal_infos[section]:
                    if field in employee_fields:
                        current_value = employee[field]
                        new_value = personal_infos[section][field]

                        if isinstance(current_value, type(new_value)) and current_value == new_value:
                            continue

                        elif employee_fields[field].relational:
                            current_value = str(current_value.name)
                            if new_value:
                                new_record = request.env[employee_fields[field].comodel_name].sudo().browse(int(new_value))
                                new_value = new_record['name'] if new_record else ''

                        elif employee_fields[field].type in ['integer', 'float']:
                            current_value = str(current_value)
                            if not new_value:
                                new_value = '0'

                        elif employee_fields[field].type == 'date':
                            current_value = current_value.strftime('%Y-%m-%d') if current_value else ''

                        elif employee_fields[field].type == 'boolean':
                            current_value = str(current_value)
                            new_value = str(new_value)

                        elif employee_fields[field].type == 'binary':
                            continue

                        if current_value != new_value:
                            employee_field_name = employee_fields[field].string or field
                            version_diff.append((employee_field_name, current_value, new_value))

        new_version = request.env['hr.version'].with_context(
            tracking_disable=True,
            salary_simulation=True,
        ).sudo().create(self._get_new_version_values(version_vals, employee, benefits_values, offer))
        self._update_personal_info(employee, new_version, personal_infos, no_name_write=bool(kw.get('employee')))

        # get differences for version information
        if no_write:
            version_fields = request.env['hr.version']._fields
            for field in version_fields:
                if field in benefits_values and version_vals.get(field) != new_version[field]\
                        and (version_vals.get(field) or new_version[field]):
                    current_value = version_vals.get(field)
                    new_value = new_version[field]
                    version_field_name = version_fields[field].string or field
                    version_diff.append((version_field_name, current_value, new_value))

        if 'original_link' in kw:
            start_date = parse_qs(urlparse(kw['original_link']).query).get('version_start_date', False)
            if start_date:
                new_version.date_version = datetime.strptime(start_date[0], '%Y-%m-%d').date()

        new_version.wage_with_holidays = benefits_values['wage']
        new_version.final_yearly_costs = float(benefits_values['final_yearly_costs'] or 0.0)
        new_version._inverse_wage_with_holidays()

        return new_version, version_diff

    @http.route('/salary_package/update_salary', type="jsonrpc", auth="public")
    def update_salary(self, offer_id=None, benefits=None, **kw):
        result = {}

        request.env.flush_all()
        with request.env.cr.savepoint(flush=False) as sp:

            offer = request.env['hr.contract.salary.offer'].sudo().browse(offer_id)
            version = offer._get_version()
            has_access, error_page = self.check_access_to_salary_configurator(kw.get('token'), offer, version)
            if not has_access:
                return error_page
            version_vals = version._get_values_dict()
            new_version = self.create_new_version(version_vals, offer_id, benefits, no_write=True)[0]
            final_yearly_costs = float(benefits['version']['final_yearly_costs'] or 0.0)
            new_gross = new_version._get_gross_from_employer_costs(final_yearly_costs)
            new_version.write({
                'wage': new_gross,
                'final_yearly_costs': final_yearly_costs,
            })

            result['new_gross'] = round(new_gross, 2)
            new_version = new_version.with_context(
                origin_version_id=version.id,
                simulation_working_schedule=kw.get('simulation_working_schedule', False))
            result.update(self._get_compute_results(new_version))

            request.env.flush_all()
            sp.rollback()
        return result

    def _get_compute_results(self, new_version):
        wage_to_apply = new_version._get_wage_to_apply()
        new_version.wage_on_signature = wage_to_apply

        result = {}
        result['wage_with_holidays'] = round(wage_to_apply, 2)
        # Allowed company ids might not be filled or request.env.user.company_ids might be wrong
        # since we are in route context, force the company to make sure we load everything
        resume_lines = request.env['hr.contract.salary.resume'].sudo().with_company(new_version.company_id).search([
            '|',
            ('structure_type_id', '=', False),
            ('structure_type_id', '=', new_version.structure_type_id.id),
            ('value_type', 'in', ['fixed', 'version', 'monthly_total', 'sum'])])

        result['resume_categories'] = [c.name for c in sorted(resume_lines.mapped('category_id'), key=lambda x: x.sequence)]
        result['resume_lines_mapped'] = defaultdict(lambda: {})

        monthly_total = 0
        monthly_total_lines = resume_lines.filtered(lambda l: l.value_type == 'monthly_total')

        uoms = {'days': _('Days'), 'percent': '%', 'currency': new_version.company_id.currency_id.symbol, 'position': new_version.company_id.currency_id.position}

        resume_explanation = False
        for resume_line in resume_lines - monthly_total_lines:
            value = 0
            uom = uoms[resume_line.uom]
            resume_explanation = False
            if resume_line.value_type == 'fixed':
                value = resume_line.fixed_value
            if resume_line.value_type == 'version':
                value = new_version[resume_line.code] if resume_line.code in new_version else 0  # noqa: SIM401
            if resume_line.value_type == 'sum':
                resume_explanation = _('Equals to the sum of the following values:\n\n%s',
                    '\n+ '.join(resume_line.benefit_ids.res_field_id.sudo().mapped('field_description')))
                for benefit in resume_line.benefit_ids:
                    if not benefit.fold_field or (benefit.fold_field and new_version[benefit.fold_field]):
                        field = benefit.field
                        value += new_version[field] if benefit.source == 'field' else new_version._get_property_input_value(benefit.salary_rule_id.code)
            if resume_line.impacts_monthly_total:
                monthly_total += value / 12.0 if resume_line.category_id.periodicity == 'yearly' else value
            try:
                value = round(float(value), 2)
            except:
                pass
            result['resume_lines_mapped'][resume_line.category_id.name][resume_line.code] = (resume_line.name, value, uom, resume_explanation, new_version.company_id.currency_id.position, resume_line.uom)
        for resume_line in monthly_total_lines:
            result['resume_lines_mapped'][resume_line.category_id.name][resume_line.code] = (resume_line.name, round(float(monthly_total), 2), uoms['currency'], uoms['position'], resume_explanation, resume_line.uom)
        return result

    @http.route(['/salary_package/onchange_benefit'], type='jsonrpc', auth='public')
    def onchange_benefit(self, benefit_field, new_value, offer_id, benefits, **kw):
        # Return a dictionary describing the new benefit configuration:
        # - new_value: The benefit new_value (same by default)
        # - description: The dynamic description corresponding to the benefit new value
        # - extra_value: A list of tuple (input name, input value) change another input due
        #                to the benefit new_value
        # Override this controllers to add customize
        # the returned value for a specific benefit
        offer = request.env['hr.contract.salary.offer'].sudo().browse(offer_id)
        request.env.flush_all()
        with request.env.cr.savepoint(flush=False) as sp:
            version = offer._get_version()
            has_access, error_page = self.check_access_to_salary_configurator(kw.get('token'), offer, version)
            if not has_access:
                return error_page
            benefit = request.env['hr.contract.salary.benefit'].sudo().search([
                ('structure_type_id', '=', version.structure_type_id.id),
                ('field', '=', benefit_field)], limit=1)
            if hasattr(version, '_get_description_%s' % benefit_field):
                description = getattr(version, '_get_description_%s' % benefit_field)(new_value)
            else:
                description = benefit.description
            request.env.flush_all()
            sp.rollback()
        return {'new_value': new_value, 'description': description, 'extra_values': False}

    @http.route(['/salary_package/onchange_personal_info'], type='jsonrpc', auth='public')
    def onchange_personal_info(self, field, value):
        # sudo as public users can't access ir.model.fields
        info = request.env['hr.contract.salary.personal.info'].sudo().search([('field', '=', field)])
        if not info.child_ids:
            return {}
        if info.value_ids:
            value = info.value_ids.filtered(lambda v: v.value == value)
            return {'hide_children': value.hide_children, 'field': field}
        return {'hide_children': not bool(value), 'field': field}

    def _get_email_info(self, version, **kw):
        wage_to_apply = version._get_wage_to_apply()

        field_names = {
            model: {
                field.name: field.field_description for field in request.env['ir.model.fields'].sudo().search([('model', '=', model)])
            } for model in ['hr.employee', 'hr.version', 'res.partner', 'res.partner.bank']}
        result = {
            _('Salary Package Summary'): {
                'General Information': [
                    (_('Employee Name'), version.employee_id.name),
                    (_('Job Position'), version.job_id.name),
                    (_('Job Title'), version.employee_id.job_title),
                    (_('Contract Type'), version.contract_type_id.name),
                    (_('Original Link'), kw.get('original_link'))
                ],
            }
        }
        # Contract Information
        version_benefits = request.env['hr.contract.salary.benefit'].sudo().search([('structure_type_id', '=', version.structure_type_id.id)])
        version_info = {benefit_type.name: [] for benefit_type in sorted(version_benefits.mapped('benefit_type_id'), key=lambda x: x.sequence)}
        for benefit in version_benefits:
            if benefit.folded and benefit.fold_field:
                value = _('Yes') if version[benefit.fold_field] else _('No')
                version_info[benefit.benefit_type_id.name].append((field_names['hr.version'][benefit.fold_field], value))
            field_name = benefit.field
            if not field_name or field_name not in version:
                continue
            field_value = version[field_name]
            if isinstance(field_value, models.BaseModel):
                field_value = field_value.name
            elif isinstance(field_value, float):
                field_value = round(field_value, 2)
            version_info[benefit.benefit_type_id.name].append((field_names['hr.version'][field_name], field_value))
            self._append_additional_benefit_info(version_info[benefit.benefit_type_id.name], version, field_names, field_name)

        # Add wage information
        version_info[_('Wage')] = [
            (_('Monthly Gross Salary'), wage_to_apply),
            (_('Annual Employer Cost'), version.final_yearly_costs),
        ]
        result[_('Contract Information:')] = version_info
        # Personal Information
        infos = request.env['hr.contract.salary.personal.info'].sudo().search([('display_type', '!=', 'document'), '|', ('structure_type_id', '=', False), ('structure_type_id', '=', version.structure_type_id.id)])
        personal_infos = {personal_info_type.name: [] for personal_info_type in sorted(infos.mapped('info_type_id'), key=lambda x: x.sequence)}
        for info in infos:
            if info.applies_on == 'employee':
                field_label = field_names['hr.employee'][info.field]
                field_value = version.employee_id[info.field]
            if info.applies_on == 'bank_account':
                field_label = field_names['res.partner.bank'][info.field]
                field_value = version.employee_id.primary_bank_account_id[info.field]
            if info.applies_on == 'version_personal':
                field_label = field_names['hr.version'][info.field]
                field_value = version[info.field]
            if isinstance(field_value, models.BaseModel):
                field_value = field_value.name
            elif isinstance(field_value, float):
                field_value = round(field_value, 2)
            personal_infos[info.info_type_id.name].append((field_label, field_value))
        result[_('Personal Information')] = personal_infos
        return {'mapped_data': result}

    def _append_additional_benefit_info(self, benefit_info, version, field_names, field_name):
        return

    def _send_mail_message(self, offer, template, kw, values, new_version_id=None):
        model = 'hr.version' if new_version_id else 'hr.contract.salary.offer'
        res_id = new_version_id or offer.id
        request.env[model].sudo().browse(res_id).message_post_with_source(
            template,
            render_values=values,
            subtype_xmlid='mail.mt_comment',
        )

    def send_email(self, offer, version, **kw):
        self._send_mail_message(
            offer,
            'hr_contract_salary.hr_contract_salary_email_template',
            kw,
            self._get_email_info(version, **kw))
        return version.id

    def send_diff_email(self, offer, differences, new_version_id, **kw):
        self._send_mail_message(
            offer,
            'hr_contract_salary.hr_contract_salary_diff_email_template',
            kw,
            {'differences': differences},
            new_version_id)

    @http.route(['/salary_package/submit'], type='jsonrpc', auth='public')
    def submit(self, offer_id=None, benefits=None, **kw):
        offer = request.env['hr.contract.salary.offer'].sudo().browse(offer_id).exists()
        if not offer.applicant_id and not offer.employee_version_id:
            raise UserError(_('This link is invalid. Please contact the HR Responsible to get a new one...'))

        request.env.flush_all()
        with request.env.cr.savepoint(flush=False) as sp:
            version = offer._get_version()
            has_access, error_page = self.check_access_to_salary_configurator(kw.get('token'), offer, version)
            if not has_access:
                return error_page
            if version.employee_id.user_id == request.env.user:
                kw['employee'] = version.employee_id
            version_vals = version._get_values_dict()
            request.env.flush_all()
            sp.rollback()

        kw['package_submit'] = True
        new_version = self.create_new_version(version_vals, offer_id, benefits, no_write=True, **kw)

        if isinstance(new_version, dict) and new_version.get('error'):
            return new_version

        new_version, version_diff = new_version

        # write on new version differences with current one
        current_version = new_version.employee_id.version_id
        if current_version:
            self.send_diff_email(offer, version_diff, new_version.id, **kw)

        self.send_email(offer, new_version, **kw)

        applicant = offer.applicant_id
        if applicant and offer.access_token:
            hash_token_access = hashlib.sha1(kw.get('token').encode("utf-8")).hexdigest()
            existing_version = request.env['hr.version'].sudo().search([
                ('applicant_id', '=', applicant.id), ('hash_token', '=', hash_token_access), ('active', '=', False)])
            existing_version.sign_request_ids.write({'state': 'canceled', 'active': False})
            existing_version.unlink()
            new_version.hash_token = hash_token_access
        elif not applicant and offer.employee_id.user_id and offer.employee_id.user_id == request.env.user and kw.get('original_link'):
            hash_token_access = hashlib.sha1(kw.get('original_link').encode("utf-8")).hexdigest()
            existing_version = request.env['hr.version'].sudo().search([
                ('employee_id', 'in', request.env.user.employee_ids.ids), ('hash_token', '=', hash_token_access), ('active', '=', False)])
            existing_version.sign_request_ids.write({'state': 'canceled', 'active': False})
            existing_version.unlink()
            new_version.hash_token = hash_token_access

        # TODO not sure about this change
        new_version.write({
            'name': 'New version - ' + new_version.employee_id.name,
            'origin_version_id': version_vals.get('id') if offer.employee_id else False,
        })
        sign_template = offer.sign_template_id
        signatories = offer.sign_template_signatories_ids
        if not sign_template:
            return {'error': 1, 'error_msg': _('No signature template defined on the version. Please contact the HR responsible.')}
        if not new_version.hr_responsible_id and 'hr' in signatories.mapped('signatory'):
            return {'error': 1, 'error_msg': _('No HR responsible defined on the job position. Please contact an administrator.')}

        # ask the contract responsible to create a sign request
        SignRequestSudo = request.env['sign.request'].with_user(new_version.hr_responsible_id).sudo()

        signatory_dict = {
            'employee': new_version.employee_id.work_contact_id.id,
            'hr': new_version.hr_responsible_id.work_contact_id.id or new_version.hr_responsible_id.partner_id.id
        }

        signatories_command = [
            Command.create(
                {'role_id': signatory.sign_role_id.id,
                 'partner_id': signatory_dict.get(signatory.signatory, signatory.partner_id.id),
                 'mail_sent_order': signatory.order})
            for signatory in signatories
        ]
        sign_request_sudo = SignRequestSudo.create({
            'template_id': sign_template.id,
            'request_item_ids': signatories_command,
            'reference': _('Signature Request - %s', new_version.name),
            'subject': _('Signature Request - %s', new_version.name),
            'reference_doc': f'hr.contract.salary.offer,{offer.id}'
        })
        sign_request_sudo.toggle_favorited()

        # Prefill the sign boxes
        sign_items = request.env['sign.item'].sudo().search([
            ('template_id', '=', sign_template.id),
            ('name', '!=', '')
        ])
        sign_values_by_role = defaultdict(lambda: defaultdict(lambda: request.env['sign.item']))
        for item in sign_items:
            try:
                new_value = None
                if item.name == 'car' and new_version.transport_mode_car:
                    if not new_version.new_car and new_version.car_id:
                        new_value = new_version.car_id.model_id.name
                    elif new_version.new_car and new_version.new_car_model_id:
                        new_value = new_version.new_car_model_id.name
                # YTI FIXME: Clean that brol
                elif item.name == 'l10n_be_group_insurance_rate':
                    new_value = 1 if new_version.get(item.name) else 0
                elif item.name == "ip_wage_rate":
                    new_value = new_value if new_version.ip else 0
                else:
                    new_values = new_version.mapped(item.name)
                    if not new_values or isinstance(new_values, models.BaseModel):
                        raise Exception
                    new_value = new_values[0]
                    if isinstance(new_value, float):
                        new_value = round(new_value, 2)
                    if item.type_id.item_type == "checkbox":
                        new_value = 'on' if new_value else 'off'
                if new_value is not None:
                    sign_values_by_role[item.responsible_id][str(item.id)] = new_value
            except Exception:
                pass
        for sign_request_item in sign_request_sudo.request_item_ids:
            if sign_request_item.role_id in sign_values_by_role:
                sign_request_item._fill(sign_values_by_role[sign_request_item.role_id])

        access_token = request.env['sign.request.item'].sudo().search([
            ('sign_request_id', '=', sign_request_sudo.id),
            ('role_id', '=', request.env.ref('hr_sign.sign_item_role_employee_signatory').id)
        ]).access_token

        if not access_token:
            employee_roles = request.env['hr.contract.signatory'].search([
                ('signatory', '=', 'employee'),
                ('offer_id', '=', offer_id),
            ], limit=1)
            if employee_roles:
                access_token = request.env['sign.request.item'].sudo().search([
                    ('sign_request_id', '=', sign_request_sudo.id),
                    ('role_id', 'in', employee_roles.sign_role_id.id),
                ]).access_token
        new_version.sign_request_ids += sign_request_sudo
        offer.sign_request_ids += sign_request_sudo

        if new_version:
            if offer.applicant_id:
                new_version.sudo().applicant_id = offer.applicant_id
            if offer.employee_version_id:
                new_version.sudo().origin_version_id = offer.employee_version_id

        return {
            'job_id': new_version.job_id.id,
            'request_id': sign_request_sudo.id,
            'token': access_token,
            'error': 0,
            'new_version_id': new_version.id
        }

    @http.route(['/salary_package/post_feedback'], type='jsonrpc', auth='public')
    def refuse(self, offer_id, feedback=None, token=None):
        offer = request.env['hr.contract.salary.offer'].sudo().browse(offer_id).exists()
        if not offer.applicant_id and not offer.employee_version_id:
            raise UserError(_('This link is invalid. Please contact the HR Responsible to get a new one...'))

        request.env.flush_all()
        with request.env.cr.savepoint(flush=False) as sp:
            version = offer._get_version()
            has_access, error_page = self.check_access_to_salary_configurator(token, offer, version)
            if not has_access:
                return error_page
            if not version and (not token or not consteq(offer.access_token, token)):
                raise UserError(_('This link is invalid. Please contact the HR Responsible to get a new one...'))

            request.env.flush_all()
            sp.rollback()

        if feedback:
            partner = offer.applicant_id.partner_id or offer.employee_id.work_contact_id
            offer.message_post(
                body=feedback,
                author_id=partner.id,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            return True
        return False
