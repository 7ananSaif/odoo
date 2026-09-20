# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging

from datetime import timedelta
from requests import request
from requests.exceptions import HTTPError
from werkzeug.urls import url_quote, url_encode

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import file_open

with file_open('l10n_be_hr_payroll_dimona/data/api_data.json') as f_api_data:
    API_DATA = json.load(f_api_data)
API_ROUTES = API_DATA['routes']['production']
DIMONA_TIMEOUT = 30

_logger = logging.getLogger(__name__)


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_be_dimona_declaration_id = fields.Many2one('l10n.be.dimona.declaration', string="Dimona In Declaration", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_last_dimona_declaration_id = fields.Many2one('l10n.be.dimona.declaration', string="Last Dimona Declaration", groups="hr_payroll.group_hr_payroll_user")

    l10n_be_needs_dimona_in = fields.Boolean(compute="_compute_l10n_be_needs_dimona_in", store=True, readonly=False)
    l10n_be_needs_dimona_update = fields.Boolean()
    l10n_be_needs_dimona_out = fields.Boolean()
    l10n_be_needs_dimona_cancel = fields.Boolean()
    l10n_be_dimona_next_action = fields.Selection(
        selection=[
            ('nothing', 'Nothing to do'),
            ('in', 'Dimona to open'),
            ('update', 'Dimona to update'),
            ('out', 'Dimona to close'),
            ('cancel', 'Dimona to cancel'),
        ],
        string="Dimona Next Action",
        default='nothing',
        compute='_compute_l10n_be_dimona_next_action',
        store=True,
        readonly=False)

    @api.depends('l10n_be_needs_dimona_in', 'l10n_be_needs_dimona_out', 'l10n_be_needs_dimona_update', 'l10n_be_needs_dimona_cancel')
    def _compute_l10n_be_dimona_next_action(self):
        for version in self:
            if version.l10n_be_needs_dimona_in:
                version.l10n_be_dimona_next_action = 'in'
            elif version.l10n_be_needs_dimona_out:
                version.l10n_be_dimona_next_action = 'out'
            elif version.l10n_be_needs_dimona_update:
                version.l10n_be_dimona_next_action = 'update'
            elif version.l10n_be_needs_dimona_cancel:
                version.l10n_be_dimona_next_action = 'cancel'
            else:
                version.l10n_be_dimona_next_action = 'nothing'

    @api.depends('l10n_be_dimona_declaration_id.state', 'contract_date_start')
    def _compute_l10n_be_needs_dimona_in(self):
        self.l10n_be_needs_dimona_in = True
        for version in self:
            if version.l10n_be_dimona_declaration_id:
                if version.l10n_be_dimona_declaration_id.state != 'B':
                    version.l10n_be_needs_dimona_in = False
                else:
                    version.l10n_be_needs_dimona_in = True
                continue
            if version.contract_date_start:
                versions_by_employee = version.employee_id._get_contract_versions(
                    date_start=version.contract_date_start,
                    date_end=version.contract_date_start,
                    domain=Domain('l10n_be_dimona_declaration_id', '!=', False))
                if versions_by_employee[version.employee_id.id][version.contract_date_start]:
                    version.l10n_be_needs_dimona_in = False
            else:
                version.l10n_be_needs_dimona_in = False

    def write(self, vals):
        trigger_fields = ['contract_date_start', 'contract_date_end', 'l10n_be_dimona_planned_hours', 'active']
        potential_update = any(field in vals for field in trigger_fields)
        if potential_update:
            old_values = {version: {field: version[field] for field in trigger_fields} for version in self}
        res = super().write(vals)
        if potential_update:
            for version in self:
                if version.contract_date_start != old_values[version]['contract_date_start'] and version.l10n_be_dimona_declaration_id:
                    version.l10n_be_needs_dimona_update = True
                if version.contract_date_end != old_values[version]['contract_date_end'] and version.l10n_be_dimona_declaration_id.date_end:
                    version.l10n_be_needs_dimona_update = True
                if version.contract_date_end != old_values[version]['contract_date_end'] and not version.l10n_be_dimona_declaration_id.date_end:
                    version.l10n_be_needs_dimona_out = True
                if version.l10n_be_dimona_planned_hours != old_values[version]['l10n_be_dimona_planned_hours']:
                    version.l10n_be_needs_dimona_update = True
                if not version.active and old_values[version]['active']:
                    version.l10n_be_needs_dimona_cancel = True
        return res

    def _dimona_declaration(self, data):
        self.ensure_one()
        access_token = self._dimona_authenticate(self.company_id)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % access_token,
        }

        try:
            response = request(**API_ROUTES['push_declaration'], json=data, headers=headers, timeout=DIMONA_TIMEOUT)
        except HTTPError as e:
            raise UserError(_('Cannot connect with the ONSS servers. Please contact an administrator. (%s)', e))

        if response.status_code == 201:
            result = response.headers
            declaration_reference = result['Location'].split('/')[-1]
            self.l10n_be_last_dimona_declaration_id = self.env['l10n.be.dimona.declaration'].create({
                'name': declaration_reference,
                'version_id': self.id,
                'employee_id': self.employee_id.id,
                'company_id': self.company_id.id,
            })
            if 'dimonaIn' in data:
                self.l10n_be_dimona_declaration_id = self.l10n_be_last_dimona_declaration_id
            self.employee_id.message_post(body=_('DIMONA declaration posted successfully, waiting validation'))
            self.env.ref('l10n_be_hr_payroll_dimona.ir_cron_check_dimona')._trigger(fields.Datetime.now() + timedelta(minutes=1))
            return

        if response.status_code == 400:
            raise UserError(_('Error with one or several invalid parameters on the POST request. Please contact an administrator. (%s)', response.text))
        if response.status_code == 401:
            raise UserError(_('The authentication token is invalid. Please contact an administrator. (%s)', response.text))
        if response.status_code == 403:
            raise UserError(_('Your user does not have the rights to make a declaration for the employer. This happens, for example, if the user does not have or no longer has a mandate for the employer. (%s)', response.text))
        if response.status_code == 500:
            raise UserError(_('Due to a technical problem at the ONSS side, the Dimona declaration could not be received by the ONSS.'))
        response.raise_for_status()

    def action_open_dimona(self):
        self.ensure_one()
        self.env['l10n.be.dimona.wizard'].create({
            'version_id': self.id,
            'employee_id': self.employee_id.id,
            'without_niss': not self.employee_id.niss,
            'declaration_type': 'in',
        }).submit_declaration()
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def action_close_dimona(self):
        self.ensure_one()
        self.env['l10n.be.dimona.wizard'].create({
            'version_id': self.id,
            'employee_id': self.employee_id.id,
            'declaration_type': 'out',
        }).submit_declaration()
        self.l10n_be_needs_dimona_out = False
        self.l10n_be_needs_dimona_cancel = False
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def _action_close_dimona(self):
        self.ensure_one()

        data = {
            "dimonaOut": {
                "periodId": int(self.l10n_be_dimona_declaration_id.name),
                "endDate": self.contract_date_end.strftime("%Y-%m-%d"),
            }
        }

        self._dimona_declaration(data)

    def action_update_dimona(self):
        self.ensure_one()
        self.env['l10n.be.dimona.wizard'].create({
            'version_id': self.id,
            'employee_id': self.employee_id.id,
            'declaration_type': 'update',
        }).submit_declaration()
        self.l10n_be_needs_dimona_update = False
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def _action_update_dimona(self):
        self.ensure_one()

        data = {
            "dimonaUpdate": {
                "periodId": int(self.l10n_be_dimona_declaration_id.name),
                "startDate": self.contract_date_start.strftime("%Y-%m-%d")
            }
        }
        if self.contract_date_end:
            data["dimonaUpdate"]["endDate"] = self.contract_date_end.strftime("%Y-%m-%d")
        if self.l10n_be_dimona_planned_hours:
            data['dimonaUpdate']["plannedHoursNumber"] = self.l10n_be_dimona_planned_hours

        self._dimona_declaration(data)

    def action_cancel_dimona(self):
        self.ensure_one()
        self.env['l10n.be.dimona.wizard'].create({
            'version_id': self.id,
            'employee_id': self.employee_id.id,
            'declaration_type': 'cancel',
        }).submit_declaration()
        self.l10n_be_needs_dimona_cancel = False
        self.l10n_be_needs_dimona_out = False
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def _action_cancel_dimona(self):
        self.ensure_one()

        data = {
            "dimonaCancel": {
                "periodId": int(self.l10n_be_dimona_declaration_id.name),
            }
        }

        self._dimona_declaration(data)

    def action_check_dimona(self):
        self.ensure_one()
        if not self.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            raise UserError(_("You don't have the right to call this action"))

        if not self.l10n_be_last_dimona_declaration_id:
            raise UserError(_("No DIMONA declaration is linked to this contract"))

        access_token = self._dimona_authenticate(self.company_id, declare=False)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % access_token,
        }
        try:
            response = request(
                API_ROUTES['get_declaration']['method'],
                API_ROUTES['get_declaration']['url'] + url_quote(self.l10n_be_last_dimona_declaration_id.name),
                headers=headers, timeout=DIMONA_TIMEOUT)
            if response.status_code == 200:
                result = response.json()
                self.l10n_be_last_dimona_declaration_id.content = result
            elif response.status_code == 400:
                raise UserError(_('Error with one or several invalid parameters on the POST request. Please contact an administrator. (%s)', response.text))
            elif response.status_code == 403:
                raise UserError(_('Your user does not have the rights to consult this declaration. This happens, for example, if the user does not have or no longer has a mandate for the employer. (%s)', response.text))
            elif response.status_code == 404:
                raise UserError(_('The declaration has been submitted but not processed yet or the declaration reference is not known. (%s)', response.text))
            elif response.status_code == 500:
                raise UserError(_('Due to a technical problem at the ONSS side, the Dimona declaration could not be received by the ONSS.'))
            response.raise_for_status()
        except HTTPError as e:
            raise UserError(_('Cannot connect with the ONSS servers. Please contact an administrator. (%s)', e))

    @api.model
    def action_fetch_all_dimona(self):
        if not self.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            raise UserError(_("You don't have the right to call this action"))

        companies = self.env['res.company'].search([
            ('onss_expeditor_number', '!=', False),
            ('onss_certificate_id', '!=', False),
            ('onss_registration_number', '!=', False),
        ])
        for company in companies:
            access_token = self._dimona_authenticate(company, declare=False)
            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer %s' % access_token,
            }

            # 1: Fetch all relations
            next_page = API_ROUTES['search_relations']['url'] + '?' + url_encode({'pageSize': 50, 'page': 1})
            relations_to_create = []
            while next_page:
                try:
                    data = {
                        "employer": {
                            "employerId": int(company.onss_registration_number),
                        },
                    }
                    _logger.info("Fetching Dimona Relations: %s", next_page)
                    response = request(
                        API_ROUTES['search_relations']['method'],
                        next_page,
                        json=data, headers=headers, timeout=DIMONA_TIMEOUT)
                    if response.status_code == 200:
                        result = response.json()
                        next_page = result.get('next', False)
                        for item in result['items']:
                            relation_reference = item['worker']['ssin']
                            existing_period = self.env['l10n.be.dimona.relation'].search([
                                ('company_id', '=', company.id),
                                ('name', '=', relation_reference)])
                            if not existing_period:
                                relations_to_create.append({
                                    'name': relation_reference,
                                    'company_id': company.id,
                                    'content': item
                                })
                            else:
                                existing_period.write({'content': item})
                    elif response.status_code == 400:
                        raise UserError(_('Error with one or several invalid parameters on the POST request. Please contact an administrator. (%s)', response.text))
                    elif response.status_code == 500:
                        raise UserError(_('Due to a technical problem at the ONSS side, the Dimona declarations could not be fetch to the ONSS.'))
                    response.raise_for_status()
                except HTTPError as e:
                    raise UserError(_('Cannot connect with the ONSS servers. Please contact an administrator. (%s)', e))
            self.env['l10n.be.dimona.relation'].create(relations_to_create)

            # 2: Fetch all periods
            next_page = API_ROUTES['search_periods']['url'] + '?' + url_encode({'pageSize': 50, 'page': 1})
            periods_to_create = []
            while next_page:
                try:
                    data = {
                        "employer": {
                            "employerId": int(company.onss_registration_number),
                        },
                    }
                    _logger.info("Fetching Dimona Periods: %s", next_page)
                    response = request(
                        API_ROUTES['search_periods']['method'],
                        next_page,
                        json=data, headers=headers, timeout=DIMONA_TIMEOUT)
                    if response.status_code == 200:
                        result = response.json()
                        next_page = result.get('next', False)
                        for item in result['items']:
                            period_reference = item['periodId']
                            existing_period = self.env['l10n.be.dimona.period'].search([
                                ('company_id', '=', company.id),
                                ('name', '=', period_reference)])
                            if not existing_period:
                                periods_to_create.append({
                                    'name': period_reference,
                                    'company_id': company.id,
                                    'content': item
                                })
                            else:
                                existing_period.write({'content': item})
                    elif response.status_code == 400:
                        raise UserError(_('Error with one or several invalid parameters on the POST request. Please contact an administrator. (%s)', response.text))
                    elif response.status_code == 500:
                        raise UserError(_('Due to a technical problem at the ONSS side, the Dimona declarations could not be fetch to the ONSS.'))
                    response.raise_for_status()
                except HTTPError as e:
                    raise UserError(_('Cannot connect with the ONSS servers. Please contact an administrator. (%s)', e))
            self.env['l10n.be.dimona.period'].create(periods_to_create)

            # 3: Fetch all declarations
            next_page = API_ROUTES['search_declarations']['url'] + '?' + url_encode({'pageSize': 50, 'page': 1})
            declarations_to_create = []
            while next_page:
                try:
                    data = {
                        "employer": {
                            "employerId": int(company.onss_registration_number),
                        },
                    }
                    _logger.info("Fetching Dimona Declarations: %s", next_page)
                    response = request(
                        API_ROUTES['search_declarations']['method'],
                        next_page,
                        json=data, headers=headers, timeout=DIMONA_TIMEOUT)
                    if response.status_code == 200:
                        result = response.json()
                        next_page = result.get('next', False)
                        for item in result['items']:
                            declaration_reference = item['declarationStatus']['declarationId']
                            existing_declaration = self.env['l10n.be.dimona.declaration'].search([
                                ('company_id', '=', company.id),
                                ('name', '=', declaration_reference)])
                            if not existing_declaration:
                                declarations_to_create.append({
                                    'name': declaration_reference,
                                    'company_id': company.id,
                                    'content': item
                                })
                            else:
                                existing_declaration.write({'content': item})
                    elif response.status_code == 400:
                        raise UserError(_('Error with one or several invalid parameters on the POST request. Please contact an administrator. (%s)', response.text))
                    elif response.status_code == 500:
                        raise UserError(_('Due to a technical problem at the ONSS side, the Dimona declarations could not be fetch to the ONSS.'))
                    response.raise_for_status()
                except HTTPError as e:
                    raise UserError(_('Cannot connect with the ONSS servers. Please contact an administrator. (%s)', e))
            self.env['l10n.be.dimona.declaration'].create(declarations_to_create)

    @api.model
    def _cron_l10n_be_check_dimona(self, batch_size=50):
        self.action_fetch_all_dimona()
