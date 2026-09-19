# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from markupsafe import Markup
from werkzeug.urls import url_quote_plus
import logging

from odoo import api, fields, models
from odoo.addons.base.models.ir_qweb import keep_query
from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document import CFDI_DATE_FORMAT
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    l10n_mx_edi_document_ids = fields.One2many(
        comodel_name='l10n_mx_edi.document', inverse_name='payslip_id', copy=False, readonly=True)
    l10n_mx_edi_cfdi_state = fields.Selection(
        selection=[
            ('sent', 'Signed'),
            ('cancel', 'Cancelled'),
        ],
        string="CFDI status", store=True, copy=False, tracking=True,
        compute="_compute_l10n_mx_edi_cfdi_state_and_attachment")
    l10n_mx_edi_cfdi_sat_state = fields.Selection(
        selection=[
            ('valid', "Validated"),
            ('cancelled', "Cancelled"),
            ('not_found', "Not Found"),
            ('not_defined', "Not Defined"),
            ('error', "Error"),
        ],
        string="SAT status", store=True, copy=False, tracking=True,
        compute="_compute_l10n_mx_edi_cfdi_state_and_attachment")
    l10n_mx_edi_cfdi_attachment_id = fields.Many2one(
        comodel_name='ir.attachment', string="CFDI", store=True, copy=False,
        compute='_compute_l10n_mx_edi_cfdi_state_and_attachment')

    l10n_mx_edi_cfdi_origin = fields.Char(
        string="CFDI Origin", copy=False, index='btree_not_null',
        help="In some cases like payments, credit notes, debit notes, invoices re-signed or invoices that are redone "
             "due to payment in advance will need this field filled, the format is:\n"
             "Origin Type|UUID1, UUID2, ...., UUIDn.\n"
             "Where the origin type could be:\n"
             "- 01: Nota de crédito\n"
             "- 02: Nota de débito de los documentos relacionados\n"
             "- 03: Devolución de mercancía sobre facturas o traslados previos\n"
             "- 04: Sustitución de los CFDI previos\n"
             "- 05: Traslados de mercancias facturados previamente\n"
             "- 06: Factura generada por los traslados previos\n"
             "- 07: CFDI por aplicación de anticipo")
    l10n_mx_edi_cfdi_uuid = fields.Char(
        string="Fiscal Folio", copy=False, store=True, tracking=True, index='btree_not_null',
        compute='_compute_l10n_mx_edi_cfdi_uuid',
        help="Folio in electronic invoice, is returned by SAT when send to stamp.")
    l10n_mx_edi_cfdi_cancel_id = fields.Many2one(
        comodel_name='hr.payslip', string="Substituted By", index='btree_not_null',
        compute='_compute_l10n_mx_edi_cfdi_cancel_id')

    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------

    @api.depends('l10n_mx_edi_document_ids.state', 'l10n_mx_edi_document_ids.sat_state')
    def _compute_l10n_mx_edi_cfdi_state_and_attachment(self):
        for payslip in self:
            payslip.l10n_mx_edi_cfdi_sat_state = False
            payslip.l10n_mx_edi_cfdi_state = False
            payslip.l10n_mx_edi_cfdi_attachment_id = False

        for payslip in self.filtered(lambda p: p.country_code == 'MX'):
            for doc in payslip.l10n_mx_edi_document_ids.sorted():
                if doc.state == 'payslip_sent':
                    payslip.l10n_mx_edi_cfdi_sat_state = doc.sat_state
                    payslip.l10n_mx_edi_cfdi_state = 'sent'
                    payslip.l10n_mx_edi_cfdi_attachment_id = doc.attachment_id
                    break
                elif doc.state == 'payslip_cancel':
                    payslip.l10n_mx_edi_cfdi_sat_state = doc.sat_state
                    payslip.l10n_mx_edi_cfdi_state = 'cancel'
                    payslip.l10n_mx_edi_cfdi_attachment_id = doc.attachment_id
                    break

    @api.depends('l10n_mx_edi_cfdi_attachment_id')
    def _compute_l10n_mx_edi_cfdi_uuid(self):
        for payslip in self:
            payslip.l10n_mx_edi_cfdi_uuid = False

        for payslip in self.filtered(lambda p: p.country_code == 'MX'):
            if payslip.l10n_mx_edi_cfdi_attachment_id:
                cfdi_infos = self.env['l10n_mx_edi.document']._decode_cfdi_attachment(payslip.l10n_mx_edi_cfdi_attachment_id.raw)
                payslip.l10n_mx_edi_cfdi_uuid = cfdi_infos.get('uuid')

    @api.depends('l10n_mx_edi_cfdi_uuid')
    def _compute_l10n_mx_edi_cfdi_cancel_id(self):
        for payslip in self:
            payslip.l10n_mx_edi_cfdi_cancel_id = False

        for payslip in self.filtered(lambda p: p.country_code == 'MX'):
            if payslip.company_id and payslip.l10n_mx_edi_cfdi_uuid:
                payslip.l10n_mx_edi_cfdi_cancel_id = payslip.search(
                    [
                        ('l10n_mx_edi_cfdi_origin', '=like', f'04|{payslip.l10n_mx_edi_cfdi_uuid}%'),
                        ('company_id', '=', payslip.company_id.id)
                    ], limit=1)

    @api.model
    def _issues_dependencies(self):
        return super()._issues_dependencies() + [
            'version_id.private_zip', 'employee_id.l10n_mx_rfc', 'company_id.l10n_mx_curp', 'company_id.l10n_mx_imss_id',
            'company_id.vat', 'move_id.state', 'version_id.contract_type_id.code', 'employee_id.registration_number',
            'employee_id.work_contact_id.state_id', 'company_id.partner_id.is_company', 'employee_id.ssnid',
            'employee_id.l10n_mx_curp', 'employee_id.bank_account_ids',
        ]

    def _get_errors_by_slip(self):
        errors_by_slip = super()._get_errors_by_slip()
        ready_for_cfdi = self.filtered(lambda s: s.country_code == 'MX' and s.state == 'paid' and s.move_id.state == 'posted')
        for slip in ready_for_cfdi:
            # -- Version Fields --
            if not slip.version_id.private_zip:
                errors_by_slip[slip].append({
                    'message': self.env._('Private ZIP required on the employee'),
                    'action_text': self.env._("Employee"),
                    'action': slip.employee_id._get_records_action(
                        name=self.env._("Employee"),
                        target='new',
                        context={**self.env.context, 'version_id': slip.version_id.id}
                    ),
                    'level': 'danger',
                })
            if not slip.version_id.contract_type_id:
                errors_by_slip[slip].append({
                    'message': self.env._('Contract Type required on the employee'),
                    'action_text': self.env._("Employee"),
                    'action': slip.employee_id._get_records_action(
                        name=self.env._("Employee"),
                        target='new',
                        context={**self.env.context, 'version_id': slip.version_id.id}
                    ),
                    'level': 'danger',
                })
            elif slip.version_id.contract_type_id.code not in ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '99']:
                errors_by_slip[slip].append({
                    'message': self.env._('Invalid Contract Type code on the employee'),
                    'action_text': self.env._("Employee"),
                    'action': slip.employee_id._get_records_action(
                        name=self.env._("Employee"),
                        target='new',
                        context={**self.env.context, 'version_id': slip.version_id.id}
                    ),
                    'level': 'danger',
                })

            # -- Employee Fields --
            if not slip.employee_id.registration_number:
                errors_by_slip[slip].append({
                    'message': self.env._('Employee Reference required on the employee'),
                    'action_text': self.env._("Employee"),
                    'action': slip.employee_id._get_records_action(
                        name=self.env._("Employee"),
                        target='new',
                        context={**self.env.context, 'version_id': slip.version_id.id}
                    ),
                    'level': 'danger',
                })
            if not slip.employee_id.l10n_mx_rfc:
                errors_by_slip[slip].append({
                    'message': self.env._('RFC required on the employee'),
                    'action_text': self.env._("Employee"),
                    'action': slip.employee_id._get_records_action(
                        name=self.env._("Employee"),
                        target='new',
                        context={**self.env.context, 'version_id': slip.version_id.id}
                    ),
                    'level': 'danger',
                })
            if not slip.employee_id.l10n_mx_curp:
                errors_by_slip[slip].append({
                    'message': self.env._('CURP required on the employee'),
                    'action_text': self.env._("Employee"),
                    'action': slip.employee_id._get_records_action(
                        name=self.env._("Employee"),
                        target='new',
                        context={**self.env.context, 'version_id': slip.version_id.id}
                    ),
                    'level': 'danger',
                })
            if not slip.employee_id.work_contact_id:
                errors_by_slip[slip].append({
                    'message': self.env._('Work Contact required on the employee'),
                    'action_text': self.env._("Employee"),
                    'action': slip.employee_id._get_records_action(
                        name=self.env._("Employee"),
                        target='new',
                        context={**self.env.context, 'version_id': slip.version_id.id}
                    ),
                    'level': 'danger',
                })
            elif not slip.employee_id.work_contact_id.state_id:
                errors_by_slip[slip].append({
                    'message': self.env._('State required on the work contact'),
                    'action_text': self.env._("Work Contact"),
                    'action': slip.employee_id.work_contact_id._get_records_action(
                        name=self.env._("Work Contact"),
                        target='new',
                    ),
                    'level': 'danger',
                })
            if not slip.employee_id.bank_account_ids:
                errors_by_slip[slip].append({
                    'message': self.env._('Bank Account required on the employee'),
                    'action_text': self.env._("Employee"),
                    'action': slip.employee_id._get_records_action(
                        name=self.env._("Employee"),
                        target='new',
                        context={**self.env.context, 'version_id': slip.version_id.id}
                    ),
                    'level': 'danger',
                })
        return errors_by_slip

    def _get_warnings_by_slip(self):
        warnings_by_slip = super()._get_warnings_by_slip()
        ready_for_cfdi = self.filtered(lambda s: s.country_code == 'MX' and s.state == 'paid' and s.move_id.state == 'posted')
        for slip in ready_for_cfdi:
            # -- Company Fields --
            if not slip.company_id.l10n_mx_curp and not slip.company_id.partner_id.is_company:
                warnings_by_slip[slip].append({
                    'message': self.env._('CURP missing on the company'),
                    'action_text': self.env._("Settings"),
                    'action': self.env['ir.actions.actions']._for_xml_id('hr_payroll.action_hr_payroll_configuration'),
                    'level': 'warning',
                })
            if not slip.company_id.l10n_mx_imss_id:
                warnings_by_slip[slip].append({
                    'message': self.env._('IMSS ID missing on the company'),
                    'action_text': self.env._("Settings"),
                    'action': self.env['ir.actions.actions']._for_xml_id('hr_payroll.action_hr_payroll_configuration'),
                    'level': 'warning',
                })
            if not slip.company_id.vat:
                warnings_by_slip[slip].append({
                    'message': self.env._('VAT missing on the company'),
                    'action_text': self.env._("Settings"),
                    'action': self.env['ir.actions.actions']._for_xml_id('account.action_account_config'),
                    'level': 'warning',
                })

            # -- Employee Fields --
            if not slip.employee_id.ssnid:
                warnings_by_slip[slip].append({
                    'message': self.env._('SSN ID missing on the employee'),
                    'action_text': self.env._("Employee"),
                    'action': slip.employee_id._get_records_action(
                        name=self.env._("Employee"),
                        target='new',
                        context={**self.env.context, 'version_id': slip.version_id.id}
                    ),
                    'level': 'warning',
                })
        return warnings_by_slip

    def _is_invalid(self):
        if self.country_code == 'MX':
            return not self.l10n_mx_edi_cfdi_uuid
        return super()._is_invalid()

    def _get_data_files_to_update(self):
        return super()._get_data_files_to_update() + [(
            'l10n_mx_hr_payroll_account_edi', [
                'data/hr_salary_rule_data.xml',
            ])]

    # -------------------------------------------------------------------------
    # CFDI Generation: Payslips
    # -------------------------------------------------------------------------

    def _l10n_mx_edi_add_payslip_cfdi_values(self, cfdi_values=None):
        self.ensure_one()
        if cfdi_values is None:
            if not self.l10n_mx_edi_cfdi_uuid:
                return defaultdict(str)
            cfdi_values = self.env['l10n_mx_edi.document']._get_company_cfdi_values(self.company_id)

        self.env['l10n_mx_edi.document']._add_base_cfdi_values(cfdi_values)
        self.env['l10n_mx_edi.document']._add_currency_cfdi_values(cfdi_values, self.currency_id)
        self.env['l10n_mx_edi.document']._add_document_origin_cfdi_values(cfdi_values, self.l10n_mx_edi_cfdi_origin)
        self.env['l10n_mx_edi.document']._add_customer_cfdi_values(cfdi_values, self.employee_id.user_partner_id)

        rules_amount = {line.salary_rule_id: abs(line.total) for line in self.line_ids}
        subsidy_rule = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_subsidy', raise_if_not_found=False)
        if subsidy_rule and subsidy_rule not in rules_amount:
            rules_amount[subsidy_rule] = 0

        mx_tz = self.employee_id._l10n_mx_edi_get_cfdi_timezone()
        cfdi_values['fecha'] = fields.Datetime.now().astimezone(mx_tz).strftime(CFDI_DATE_FORMAT)
        cfdi_values['tipo_de_comprobante'] = 'N'
        cfdi_values['serie'], _, cfdi_values['folio'] = self.move_id.name.rpartition('/')
        periodicity = self.version_id.l10n_mx_payment_periodicity if self.struct_id.l10n_mx_payroll_type == 'O' else '99'
        periodicity_label = dict(self.version_id._fields['l10n_mx_payment_periodicity'].selection).get(periodicity)
        cfdi_values['periodo'] = f'{periodicity} - {periodicity_label}'

        cfdi_values['receptor'] = {
            'rfc': self.employee_id.l10n_mx_rfc,
            'nombre': self.env['l10n_mx_edi.document']._cfdi_sanitize_to_legal_name(self.employee_id.legal_name),
            'domicilio_fiscal_receptor': self.employee_id.private_zip,
        }

        cfdi_values['nomina'] = nomina = {
            'tipo_nomina': self.struct_id.l10n_mx_payroll_type,
            'fecha_pago': self.paid_date.isoformat(),
            'fecha_inicial_pago': self.date_from.isoformat(),
            'fecha_final_pago': self.date_to.isoformat(),
            'num_dias_pagados': (self.date_to - self.date_from).days + 1,
        }

        cfdi_values['nomina_emisor'] = {
            'curp': self.company_id.l10n_mx_curp if not self.company_id.partner_id.is_company else False,
            'registro_patronal': self.company_id.l10n_mx_imss_id,
            'rfc_patron_origen': self.company_id.vat,
        }

        bank_account = self.employee_id.bank_account_ids[0]
        bank_account_number = bank_account.l10n_mx_edi_clabe or bank_account.acc_number
        is_clabe = len(bank_account_number) == 18
        integrated_daily_wage_rule = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_integrated_daily_wage', raise_if_not_found=False)
        integrated_daily_wage = rules_amount[integrated_daily_wage_rule] if integrated_daily_wage_rule and integrated_daily_wage_rule in rules_amount else 0
        cfdi_values['nomina_receptor'] = {
            'curp': self.employee_id.l10n_mx_curp,
            'num_seguridad_social': self.employee_id.ssnid,
            'fecha_inicio_rel_laboral': self.version_id.contract_date_start.isoformat(),
            'antigüedad': f'P{(self.date_to - self.version_id.contract_date_start).days // 7}W',
            'tipo_contrato': self.version_id.contract_type_id.code,
            'tipo_regimen': self.version_id.l10n_mx_regime_type,
            'tipo_jornada': self.version_id.l10n_mx_shift_type,
            'num_empleado': self.employee_id.registration_number,
            'riesgo_puesto': self.company_id.l10n_mx_risk_type,
            'periodicidad_pago': periodicity,
            'puesto': self.version_id.job_title,
            'departamento': self.version_id.department_id.name if self.version_id.department_id else False,
            'salario_base_cot_apor': integrated_daily_wage,
            'salario_diario_integrado': self.l10n_mx_daily_salary,
            'clave_ent_fed': self.employee_id.work_contact_id.state_id.code,
            'cuenta_bancaria': bank_account_number,
            'banco': bank_account.bank_id.l10n_mx_edi_code if not is_clabe else 0,
        }

        cfdi_values['percepcion_list'] = perceptions = []
        total_salaries = total_taxable = total_exempt = total_severance_pay = 0
        cfdi_values['deduccion_list'] = deductions = []
        total_taxes_withheld = total_other_deductions = 0
        cfdi_values['otro_pago_list'] = other_payments = []
        total_other_payments = 0

        rules = self.line_ids.salary_rule_id
        if 'SUBSIDY' not in rules.mapped('code'):
            rules |= self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_subsidy', raise_if_not_found=False)
        for rule in rules:
            concept = rule.l10n_mx_concept
            if not concept:
                continue

            amount = rules_amount.get(rule, 0)
            if not amount and not (concept.cfdi_type == 'other' and concept.sat_code == '002'):
                continue

            # == PERCEPTIONS ==
            if concept.cfdi_type == 'perception':
                perceptions.append({
                    'tipo_percepcion': concept.sat_code,
                    'clave': concept.payroll_code,
                    'concepto': concept.name,
                    'importe_gravado': amount if concept.is_taxable else 0,
                    'importe_exento': amount if not concept.is_taxable else 0,
                })

                if concept.is_taxable:
                    total_taxable += amount
                else:
                    total_exempt += amount
                if concept.sat_code not in ['022', '023', '025', '039', '044']:
                    total_salaries += amount
                if concept.sat_code in ['022', '023', '025']:
                    total_severance_pay += amount

            # == DEDUCTIONS ==
            elif concept.cfdi_type == 'deduction':
                deductions.append({
                    'tipo_deduccion': concept.sat_code,
                    'clave': concept.payroll_code,
                    'concepto': concept.name,
                    'importe': amount,
                })

                if concept.sat_code == '002':
                    total_taxes_withheld += amount
                else:
                    total_other_deductions += amount

            # == OTHER PAYMENTS ==
            else:
                other_payments.append({
                    'tipo_otro_pago': concept.sat_code,
                    'clave': concept.payroll_code,
                    'concepto': concept.name,
                    'importe': amount,
                    'subsidio_causado': amount if concept.sat_code == '002' else 0,
                    'saldo_a_favor': amount if concept.sat_code == '001' else 0,
                    'año': self.date_from.year,
                    'remanente_sal_fav': 0.0,
                })
                total_other_payments += amount

        # == SUB TOTALS ==
        total_perceptions = total_salaries + total_severance_pay
        nomina['total_percepciones'] = total_perceptions
        cfdi_values['nomina_percepciones'] = {
            'total_sueldos': total_salaries,
            'total_gravado': total_taxable,
            'total_exento': total_exempt,
        }

        total_deductions = total_taxes_withheld + total_other_deductions
        nomina['total_deducciones'] = total_deductions
        cfdi_values['nomina_deducciones'] = {
            'total_otras_deducciones': total_other_deductions,
            'total_impuestos_retenidos': total_taxes_withheld,
        }

        nomina['total_otros_pagos'] = total_other_payments

        # == INCAPACITIES ==
        cfdi_values['incapacidad_list'] = incapacities = []
        incapacities_days_by_code = defaultdict(int)
        for worked_days in self.worked_days_line_ids:
            if code := worked_days.work_entry_type_id.l10n_mx_sat_code:
                incapacities_days_by_code[code] += worked_days.number_of_days
        for code, days in incapacities_days_by_code.items():
            incapacities.append({
                'tipo_incapacidad': code,
                'dias_incapacidad': days,
            })

        # == TOTALS ==
        cfdi_values['concepto'] = {
            'valor_unitario': total_perceptions + total_other_payments,
            'importe': total_perceptions + total_other_payments,
            'descuento': total_deductions,
        }

        cfdi_values['subtotal'] = total_perceptions + total_other_payments
        cfdi_values['descuento'] = total_deductions
        cfdi_values['total'] = cfdi_values['subtotal'] - cfdi_values['descuento']
        return cfdi_values

    # -------------------------------------------------------------------------
    # CFDI: DOCUMENTS
    # -------------------------------------------------------------------------

    def action_generate_cfdi(self):
        if self.filtered('error_count'):
            raise ValidationError(self._get_error_message())
        self._l10n_mx_edi_cfdi_try_send()
        if self.l10n_mx_edi_cfdi_uuid:
            self.action_print_cfdi()

    def action_print_cfdi(self):
        self._generate_pdf()

    def _l10n_mx_edi_get_cfdi_filename(self):
        return f"{self.move_id.name}-MX-Nómina-12.xml".replace('/', '-')

    def _l10n_mx_edi_cfdi_try_send(self):
        """ Try to generate and send the CFDI for the current payslip. """
        self.ensure_one()
        if (self.state != 'paid' or not self.move_id or not self.move_id.name or
                self.l10n_mx_edi_cfdi_state not in (False, 'cancel')):
            return

        # == Check the config ==
        error = ""
        currency_precision = self.currency_id.l10n_mx_edi_decimal_places
        if not currency_precision:
            error = self.env._(
                "The SAT does not provide information for the currency %s.\n"
                "You must get manually a key from the PAC to confirm the "
                "currency rate is accurate enough.",
                self.currency_id)
        if error:
            self._l10n_mx_edi_cfdi_sent_failed(error)
            return

        # == Lock ==
        self.env['res.company']._with_locked_records(self)

        # == Send ==
        def on_populate(cfdi_values):
            self._l10n_mx_edi_add_payslip_cfdi_values(cfdi_values)

        def on_failure(error, cfdi_filename=None, cfdi_str=None):
            document = self._l10n_mx_edi_cfdi_sent_failed(error, cfdi_filename=cfdi_filename, cfdi_str=cfdi_str)
            _logger.error('An error occurred while signing the CFDI document with the government.\n%s\n', error)
            self.message_post(
                body=self.env._(
                    "An error occurred while signing the CFDI document with the government:%(error)s",
                    error=Markup("<br/><b>%s</b>") % error),
                attachment_ids=document.attachment_id.ids)

        def on_success(_cfdi_values, cfdi_filename, cfdi_str, populate_return=None):
            document = self._l10n_mx_edi_cfdi_sent(cfdi_filename, cfdi_str)
            self.message_post(
                body=self.env._("The CFDI document was successfully created and signed by the government."),
                attachment_ids=document.attachment_id.ids)
            self.move_id.l10n_mx_edi_cfdi_uuid = self.l10n_mx_edi_cfdi_uuid

        self.env['l10n_mx_edi.document']._send_api(
            self.company_id,
            'l10n_mx_hr_payroll_account_edi.cfdiv40_nomina',
            self._l10n_mx_edi_get_cfdi_filename(),
            on_populate,
            on_failure,
            on_success,
        )

    def _l10n_mx_edi_cfdi_sent(self, cfdi_filename, cfdi_str):
        """ Create/update the payslip document for 'sent'.

        :param cfdi_filename:   The filename of the cfdi.
        :param cfdi_str:        The content of the cfdi.
        """
        self.ensure_one()

        document_values = {
            'payslip_id': self.id,
            'state': 'payslip_sent',
            'sat_state': 'not_defined',
            'message': None,
            'attachment_id': {
                'name': cfdi_filename,
                'raw': cfdi_str,
                'res_model': self._name,
                'res_id': self.id,
                'description': "CFDI",
            },
        }
        return self.env['l10n_mx_edi.document']._create_update_payslip_document(self, document_values)

    def _l10n_mx_edi_cfdi_sent_failed(self, error, cfdi_filename=None, cfdi_str=None):
        """ Create/update the payslip document for 'sent_failed'.

        :param error:           The error.
        :param cfdi_filename:   The optional filename of the cfdi.
        :param cfdi_str:        The optional content of the cfdi.
        :return:                The created/updated document.
        """
        self.ensure_one()

        document_values = {
            'payslip_id': self.id,
            'state': 'payslip_sent_failed',
            'sat_state': None,
            'message': error,
        }
        if cfdi_filename and cfdi_str:
            document_values['attachment_id'] = {
                'name': cfdi_filename,
                'raw': cfdi_str,
            }
        return self.env['l10n_mx_edi.document']._create_update_payslip_document(self, document_values)

    def _l10n_mx_edi_get_extra_report_values(self):
        cfdi_infos = self.env['l10n_mx_edi.document']._decode_cfdi_attachment(self.l10n_mx_edi_cfdi_attachment_id.raw)
        if not cfdi_infos:
            return {}

        barcode_value_params = keep_query(
            id=cfdi_infos['uuid'],
            re=cfdi_infos['supplier_rfc'],
            rr=cfdi_infos['customer_rfc'],
            tt=cfdi_infos['amount_total'],
        )
        barcode_sello = url_quote_plus(cfdi_infos['sello'][-8:], safe='=/').replace('%2B', '+')
        barcode_value = url_quote_plus(f'https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?{barcode_value_params}&fe={barcode_sello}')
        barcode_src = f'/report/barcode/?barcode_type=QR&value={barcode_value}&width=180&height=180'

        return {
            **cfdi_infos,
            'barcode_src': barcode_src,
        }
