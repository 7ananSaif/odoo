from markupsafe import Markup
from odoo import models, fields
from odoo.tools import LazyTranslate
_lt = LazyTranslate(__name__)

AGENCIA_URL = 'https://sede.agenciatributaria.gob.es/'
LOGIN_PREFIX = _lt("Log in to the Spanish Tax Agency's portal:")
AGENCIA_LABEL = _lt("Agencia Tributaria")
IMPORT_INSTRUCTIONS = _lt("Choose the option to file by importing a file ('Importar') and upload the generated file when prompted.")
INSTRUCTIONS_BY_MODELO = {
    'l10n_es_reports_2025.mod111.submission.wizard': {
        'navigate': _lt("Navigate to the appropriate section for tax returns and select 'Modelo 111'."),
        'review': _lt("Review the imported data and submit the declaration using your digital certificate or Cl@ve PIN."),
    },
    'l10n_es_reports_2025.mod115.submission.wizard': {
        'navigate': _lt("Navigate to 'Impuestos y tasas' → 'Declaraciones' and select 'Modelo 115'."),
        'review': _lt("Review the imported data and submit with your digital certificate or Cl@ve PIN."),
    },
    'l10n_es_reports_2025.mod130.submission.wizard': {
        'navigate': _lt("Navigate to 'Impuestos y tasas' → 'Declaraciones' and select 'Modelo 130'."),
        'review': _lt("Review the imported data, complete the payment details if applicable, and submit with your digital certificate or Cl@ve PIN."),
    },
    'l10n_es_reports_2025.mod303.submission.wizard': {
        'navigate': _lt("Navigate to 'IVA' and select 'Modelo 303'."),
        'review': _lt("Review all the data, especially totals and bank details, then submit with your digital certificate or Cl@ve PIN."),
    },
    'l10n_es_reports_2025.mod347.submission.wizard': {
        'navigate': _lt("Navigate to 'Declaraciones informativas' and select 'Modelo 347'."),
        'review': _lt("Review the imported data for accuracy and submit with your digital certificate or Cl@ve PIN."),
    },
    'l10n_es_reports_2025.mod349.submission.wizard': {
        'navigate': _lt("Navigate to the section for tax returns and find the form 'Modelo 349'."),
        'review': _lt("Review and submit the declaration using your digital certificate or Cl@ve PIN."),
    },
    'l10n_es_reports_2025.mod390.submission.wizard': {
        'navigate': _lt("Navigate to 'IVA' and select 'Modelo 390'."),
        'review': _lt("Carefully review all fields, ensuring the annual totals match your records, then submit with your digital certificate or Cl@ve PIN."),
    },
}


class L10nEsReportsModelosSubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports_2025.modelos.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = 'Generic BOE Submission Wizard'

    submission_instructions = fields.Html(
        string="Submission Instructions",
        compute='_compute_submission_instructions',
    )

    def _compute_submission_instructions(self):
        for wizard in self:
            parts = []
            parts.append(Markup('<li>%s <a href="%s" target="_blank">%s</a>.</li>') % (LOGIN_PREFIX, AGENCIA_URL, AGENCIA_LABEL))
            specific_instructions = INSTRUCTIONS_BY_MODELO.get(wizard._name, {})
            if specific_instructions:
                parts.append(Markup('<li>%s</li>') % specific_instructions.get('navigate'))
                parts.append(Markup('<li>%s</li>') % IMPORT_INSTRUCTIONS)
                parts.append(Markup('<li>%s</li>') % specific_instructions.get('review'))
                wizard.submission_instructions = ''.join(parts)

    def export_boe(self):
        boe_file = self.return_id.attachment_ids.filtered(lambda a: a.name.endswith(".txt"))
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{boe_file.id}?download=true",
            "target": "download",
        }


class L10n_Es_ReportsMod111SubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports_2025.mod111.submission.wizard'
    _inherit = 'l10n_es_reports_2025.modelos.submission.wizard'
    _description = "BOE Submission Wizard for (mod111)"


class L10n_Es_ReportsMod115SubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports_2025.mod115.submission.wizard'
    _inherit = 'l10n_es_reports_2025.modelos.submission.wizard'
    _description = "BOE Submission Wizard for (mod115)"


class L10n_Es_ReportsMod130SubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports_2025.mod130.submission.wizard'
    _inherit = 'l10n_es_reports_2025.modelos.submission.wizard'
    _description = "BOE Submission Wizard for (mod130)"


class L10n_Es_ReportsMod303SubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports_2025.mod303.submission.wizard'
    _inherit = 'l10n_es_reports_2025.modelos.submission.wizard'
    _description = "BOE Submission Wizard for (mod303)"


class L10n_Es_ReportsMod347SubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports_2025.mod347.submission.wizard'
    _inherit = 'l10n_es_reports_2025.modelos.submission.wizard'
    _description = "BOE Submission Wizard for (mod347)"


class L10n_Es_ReportsMod349SubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports_2025.mod349.submission.wizard'
    _inherit = 'l10n_es_reports_2025.modelos.submission.wizard'
    _description = "BOE Submission Wizard for (mod349)"


class L10n_Es_ReportsMod390SubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports_2025.mod390.submission.wizard'
    _inherit = 'l10n_es_reports_2025.modelos.submission.wizard'
    _description = "BOE Submission Wizard for (mod390)"
