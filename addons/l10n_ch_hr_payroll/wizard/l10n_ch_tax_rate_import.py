# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Source: https://www.estv.admin.ch/estv/fr/accueil/impot-federal-direct/impot-a-la-source/baremes-cantonaux.html

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from collections import defaultdict
from datetime import date

import base64
import logging
import requests
import zipfile
import io

_logger = logging.getLogger(__name__)

CANTON_CODES = [
    'AG', 'AI', 'AR', 'BE', 'BL', 'BS', 'FR', 'GE', 'GL', 'GR', 'JU', 'LU', 'NE', 'NW', 'OW',
    'SG', 'SH', 'SO', 'SZ', 'TG', 'TI', 'UR', 'VD', 'VS', 'ZG', 'ZH']
TAX_SCALES = list('ABCDEFGHIJKLMNOPQRSTUV')


class L10nChTaxRateImportWizard(models.TransientModel):
    _name = 'l10n.ch.tax.rate.import.wizard'
    _description = 'Swiss Payroll: Tax rate import wizard'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "CH":
            raise UserError(_('You must be logged into a Swiss company to use this feature'))
        return super().default_get(fields)

    tax_file_ids = fields.One2many('ir.attachment', 'res_id',
        domain=[('res_model', '=', 'l10n.ch.tax.rate.import.wizard')],
        string='Tax Files')
    import_mode = fields.Selection(selection=[('manual', 'Manual File Import'),
                                              ('automatic', 'Automatic Import')], required=True, default='automatic')

    canton_mode = fields.Selection([
        ('all', 'Import every canton'),
        ('single', 'Import one canton'),
    ], string='Canton Importation',
       default='all',
       required=True,
       help="Select whether to import tax rates for all cantons at once, or for a single canton.")
    canton = fields.Selection([
        ('AG', 'AG'), ('AI', 'AI'), ('AR', 'AR'), ('BE', 'BE'), ('BL', 'BL'), ('BS', 'BS'),
        ('FR', 'FR'), ('GE', 'GE'), ('GL', 'GL'), ('GR', 'GR'), ('JU', 'JU'), ('LU', 'LU'),
        ('NE', 'NE'), ('NW', 'NW'), ('OW', 'OW'), ('SG', 'SG'), ('SH', 'SH'), ('SO', 'SO'),
        ('SZ', 'SZ'), ('TG', 'TG'), ('TI', 'TI'), ('UR', 'UR'), ('VD', 'VD'), ('VS', 'VS'),
        ('ZG', 'ZG'), ('ZH', 'ZH'),
    ], string='Canton',
       default='GE',
       help="Canton for which to download the official tax file (only relevant if you choose 'Import one canton').")
    year = fields.Integer(
        string='Tax Year',
        default=lambda self: fields.Date.today().year,
        required=True,
        help='Year for which to download the tax rate file'
    )

    def action_import_file(self):
        self.ensure_one()
        if not self.tax_file_ids:
            raise UserError(_('Please upload a tax file first.'))
        count = 0
        for tax_file in self.tax_file_ids:
            count += 1
            _logger.info("Importing swiss tax file %s/%s", count, len(self.tax_file_ids))
            tax_file_content = base64.b64decode(tax_file.datas).decode('utf-8')
            # {(canton, date_from, church_tax, tax_scale, child_count): [(low, high, min_amount, rate)]}
            mapped_rates = defaultdict(list)
            mapped_predefined_categories_rates = defaultdict(list)
            mapped_specific_codes = defaultdict(list)
            for line in tax_file_content.split('\r\n'):
                line_type = line[0:2]
                if line_type in ['00', '99']:
                    # Initial line containing canton name and file creation date (not needed)
                    continue
                if line_type not in ['06', '11', '12', '13']:
                    raise UserError(_('Unrecognized line format: %s', line))
                # Progressive scales of withholding tax
                transaction_type = line[2:4]
                if transaction_type == '01':
                    # New announce, ok
                    pass
                elif transaction_type == '02':
                    # modification
                    raise UserError(_('Unmanaged transaction type 02: %(line)', line=line))
                elif transaction_type == '03':
                    # Removal
                    raise UserError(_('Unmanaged transaction type 03: %(line)', line=line))
                else:
                    raise UserError(_('Unrecognized transaction type %(t_type): %(line)', t_type=transaction_type, line=line))

                canton = line[4:6]
                if canton not in CANTON_CODES:
                    raise UserError(_('Unrecognized canton code %(canton): %(line)', canton=canton, line=line))

                tax_code = line[6:16].strip()
                if line_type == "06":
                    tax_scale = tax_code[0]
                    if tax_scale not in TAX_SCALES:
                        raise UserError(_('Unrecognized tax scale %(tax_scale): %(line)', tax_scale=tax_scale, line=line))
                    child_count = int(tax_code[1])
                church_tax = tax_code[2]  # 'Y' or 'N'

                date_from = line[16:24]
                date_from = date(int(date_from[0:4]), int(date_from[4:6]), int(date_from[6:8]))

                wage_from = line[24:33]
                wage_from = int(wage_from) / 100.0

                tariff_scale = line[33:42]
                tariff_scale = int(tariff_scale) / 100.0

                low = wage_from
                high = wage_from - 1 + tariff_scale

                tax_min_amount = line[45:54]
                tax_min_amount = int(tax_min_amount) / 100.0

                tax_rate = line[54:59]
                tax_rate = int(tax_rate) / 100.0  # 000715 -> 7.15M%

                if line_type == "06":
                    mapped_rates[(canton, date_from, church_tax, tax_scale, child_count)].append(
                        (low, high, tax_min_amount, tax_rate)
                    )
                elif line_type == "11":
                    mapped_predefined_categories_rates[(canton, date_from, tax_code[0:2], church_tax)].append(
                        (low, high, tax_min_amount, tax_rate)
                    )
                else:
                    mapped_specific_codes[(canton, date_from, tax_code)].append(
                        (low, high, tax_min_amount, tax_rate)
                    )

            for (canton, date_from, church_tax, tax_scale, child_count), parameter_values in mapped_rates.items():
                parameter_xmlid = f"rule_parameter_withholding_tax_{canton}_{church_tax}_{tax_scale}_{child_count}"
                parameter = self.env['hr.rule.parameter'].search([
                    ('code', '=', f'l10n_ch_withholding_tax_rates_{canton}_{church_tax}_{tax_scale}_{child_count}')
                ], limit=1)
                if not parameter:
                    parameter = self.env['hr.rule.parameter'].create({
                        'name': f"CH Withholding Tax: Canton ({canton}) - Church _tax ({church_tax}) - Tax Scale ({tax_scale}) - Children ({child_count})",
                        'code': f'l10n_ch_withholding_tax_rates_{canton}_{church_tax}_{tax_scale}_{child_count}',
                        'country_id': self.env.ref('base.ch').id,
                    })

                    ir_model_data = self.env['ir.model.data'].search([('name', '=', parameter_xmlid), ('module', '=', 'l10n_ch_hr_payroll'), ('model', '=', 'hr.rule.parameter')])
                    if ir_model_data:
                        ir_model_data.write({
                            'res_id': parameter.id
                        })
                    else:
                        self.env['ir.model.data'].create({
                            'name': parameter_xmlid,
                            'module': 'l10n_ch_hr_payroll',
                            'res_id': parameter.id,
                            'model': 'hr.rule.parameter',
                            # noupdate is set to true to avoid to delete record at module update
                            'noupdate': True,
                        })
                parameter_value_data = (canton, date_from.year, date_from.month, date_from.day, church_tax, tax_scale, child_count)
                parameter_value_xmlid = "rule_parameter_value_withholding_tax_%s_%s_%s_%s_%s_%s_%s" % parameter_value_data
                parameter_value = parameter.parameter_version_ids.filtered(lambda p: p.date_from == date_from)

                if not parameter_value:
                    parameter_value = self.env['hr.rule.parameter.value'].create({
                        'parameter_value': str(parameter_values),
                        'rule_parameter_id': parameter.id,
                        'date_from': date_from,
                    })
                    ir_model_data = self.env['ir.model.data'].search([('name', '=', parameter_value_xmlid), ('module', '=', 'l10n_ch_hr_payroll'), ('model', '=', 'hr.rule.parameter.value')])
                    if ir_model_data:
                        ir_model_data.write({
                            'res_id': parameter_value.id
                        })
                    else:
                        self.env['ir.model.data'].create({
                            'name': parameter_value_xmlid,
                            'module': 'l10n_ch_hr_payroll',
                            'res_id': parameter_value.id,
                            'model': 'hr.rule.parameter.value',
                            # noupdate is set to true to avoid to delete record at module update
                            'noupdate': True,
                        })
                else:
                    parameter_value.write({'parameter_value': str(parameter_values)})

            for (canton, date_from, tax_code, church_tax), parameter_values in mapped_predefined_categories_rates.items():
                # Predefined categories
                parameter_xmlid = f"rule_parameter_withholding_tax_{canton}_{tax_code}_{church_tax}"
                parameter = self.env['hr.rule.parameter'].search([
                    ('code', '=', f'l10n_ch_withholding_tax_rates_{canton}_{tax_code}_{church_tax}')
                ], limit=1)

                if not parameter:
                    parameter = self.env['hr.rule.parameter'].create({
                        'name': f"CH Withholding Tax: Canton ({canton}) - Predefined Category ({tax_code}) - Church Tax ({church_tax})",
                        'code': f'l10n_ch_withholding_tax_rates_{canton}_{tax_code}_{church_tax}',
                        'country_id': self.env.ref('base.ch').id,
                    })
                    ir_model_data = self.env['ir.model.data'].search([('name', '=', parameter_xmlid), ('module', '=', 'l10n_ch_hr_payroll'), ('model', '=', 'hr.rule.parameter')])
                    if ir_model_data:
                        ir_model_data.write({
                            'res_id': parameter.id
                        })
                    else:
                        self.env['ir.model.data'].create({
                            'name': parameter_xmlid,
                            'module': 'l10n_ch_hr_payroll',
                            'res_id': parameter.id,
                            'model': 'hr.rule.parameter',
                            # noupdate is set to true to avoid to delete record at module update
                            'noupdate': True,
                        })

                parameter_value_data = (canton, date_from.year, date_from.month, date_from.day, tax_code, church_tax)
                parameter_value_xmlid = "rule_parameter_value_withholding_tax_%s_%s_%s_%s_%s_%s" % parameter_value_data
                parameter_value = parameter.parameter_version_ids.filtered(lambda p: p.date_from == date_from)

                if not parameter_value:
                    parameter_value = self.env['hr.rule.parameter.value'].create({
                        'parameter_value': str(parameter_values),
                        'rule_parameter_id': parameter.id,
                        'date_from': date_from,
                    })
                    ir_model_data = self.env['ir.model.data'].search([('name', '=', parameter_value_xmlid), ('module', '=', 'l10n_ch_hr_payroll'), ('model', '=', 'hr.rule.parameter.value')])
                    if ir_model_data:
                        ir_model_data.write({
                            'res_id': parameter_value.id
                        })
                    else:
                        self.env['ir.model.data'].create({
                            'name': parameter_value_xmlid,
                            'module': 'l10n_ch_hr_payroll',
                            'res_id': parameter_value.id,
                            'model': 'hr.rule.parameter.value',
                            # noupdate is set to true to avoid to delete record at module update
                            'noupdate': True,
                        })
                else:
                    parameter_value.write({'parameter_value': str(parameter_values)})

            for (canton, date_from, tax_code), parameter_values in mapped_specific_codes.items():
                # Predefined categories
                parameter_xmlid = f"rule_parameter_withholding_tax_{canton}_{tax_code}"
                parameter = self.env['hr.rule.parameter'].search([
                    ('code', '=', f'l10n_ch_withholding_tax_rates_{canton}_{tax_code}')
                ], limit=1)

                if not parameter:
                    parameter = self.env['hr.rule.parameter'].create({
                        'name': f"CH Withholding Tax: Canton ({canton}) - Predefined Category ({tax_code})",
                        'code': f'l10n_ch_withholding_tax_rates_{canton}_{tax_code}',
                        'country_id': self.env.ref('base.ch').id,
                    })
                    ir_model_data = self.env['ir.model.data'].search([('name', '=', parameter_xmlid), ('module', '=', 'l10n_ch_hr_payroll'), ('model', '=', 'hr.rule.parameter')])
                    if ir_model_data:
                        ir_model_data.write({
                            'res_id': parameter.id
                        })
                    else:
                        self.env['ir.model.data'].create({
                            'name': parameter_xmlid,
                            'module': 'l10n_ch_hr_payroll',
                            'res_id': parameter.id,
                            'model': 'hr.rule.parameter',
                            # noupdate is set to true to avoid to delete record at module update
                            'noupdate': True,
                        })
                parameter_value_data = (canton, date_from.year, date_from.month, date_from.day, tax_code)
                parameter_value_xmlid = "rule_parameter_value_withholding_tax_%s_%s_%s_%s_%s" % parameter_value_data
                parameter_value = parameter.parameter_version_ids.filtered(lambda p: p.date_from == date_from)

                if not parameter_value:
                    parameter_value = self.env['hr.rule.parameter.value'].create({
                        'parameter_value': str(parameter_values),
                        'rule_parameter_id': parameter.id,
                        'date_from': date_from,
                    })
                    ir_model_data = self.env['ir.model.data'].search([('name', '=', parameter_value_xmlid), ('module', '=', 'l10n_ch_hr_payroll'), ('model', '=', 'hr.rule.parameter.value')])
                    if ir_model_data:
                        ir_model_data.write({
                            'res_id': parameter_value.id
                        })
                    else:
                        self.env['ir.model.data'].create({
                            'name': parameter_value_xmlid,
                            'module': 'l10n_ch_hr_payroll',
                            'res_id': parameter_value.id,
                            'model': 'hr.rule.parameter.value',
                            # noupdate is set to true to avoid to delete record at module update
                            'noupdate': True,
                        })
                else:
                    parameter_value.write({'parameter_value': str(parameter_values)})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _('The tax file has been successfully imported.'),
            }
        }

    def action_import_from_website(self):
        """
        1. Build the URL based on whether we want a single canton or all cantons.
        2. Download the ZIP from ESTV.
        3. Extract all .txt files inside it, attach them to this wizard record.
        4. Call the original `action_import_file()` to parse + import as usual.
        """
        self.ensure_one()
        url = self._build_estv_download_url()
        _logger.info("Downloading Swiss tax ZIP from %s", url)

        # 2) Download the ZIP
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except Exception:  # noqa: BLE001
            raise UserError(_("Could not download file from URL"))

        zip_bytes = io.BytesIO(response.content)
        try:
            with zipfile.ZipFile(zip_bytes, 'r') as z:
                for file_name in z.namelist():
                    if file_name.lower().endswith('.txt'):
                        txt_bytes = z.read(file_name)
                        self.env['ir.attachment'].create({
                            'name': file_name,
                            'res_model': self._name,
                            'res_id': self.id,
                            'datas': base64.b64encode(txt_bytes),
                            'mimetype': 'text/plain',
                        })
                        _logger.info("Attached file %s to wizard", file_name)
        except zipfile.BadZipFile:
            raise UserError(_("Downloaded file is not a valid ZIP or is corrupted."))

        return self.action_import_file()

    def _build_estv_download_url(self):
        """
        Return the official ESTV URL based on year + whether we want all or single canton.
        """
        year_str = str(self.year)
        short_year_str = year_str[-2:]
        canton_lower = (self.canton or '').lower()

        if self.canton_mode == 'all':
            # e.g. 2025 =>
            # https://www.estv.admin.ch/dam/estv/fr/dokumente/qst/schweiz/qst-ch-tar2025txt-fr.zip.download.zip/qst-ch-tar2025txt-fr.zip
            url = (
                "https://www.estv.admin.ch/dam/estv/fr/dokumente/qst/schweiz/"
                f"qst-ch-tar{year_str}txt-fr.zip.download.zip/qst-ch-tar{year_str}txt-fr.zip"
            )
        else:
            # Single canton approach
            # https://www.estv.admin.ch/dam/estv/fr/dokumente/qst/2025/qst-loehne/qst-tar25ar-fr.zip.download.zip/qst-tar25ar-fr.zip
            url = (
                f"https://www.estv.admin.ch/dam/estv/fr/dokumente/qst/{year_str}/qst-loehne/"
                f"qst-tar{short_year_str}{canton_lower}-fr.zip.download.zip/"
                f"qst-tar{short_year_str}{canton_lower}-fr.zip"
            )
        return url
