# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import api, fields, models, _
from odoo.fields import Domain


class L10nBeDimonaDeclaration(models.Model):
    _name = 'l10n.be.dimona.declaration'
    _description = 'Dimona Declaration'

    name = fields.Char('Declaration ID', required=True, readonly=True, index=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True, index=True)
    content = fields.Json()
    declaration_type = fields.Selection([
        ('dimona_in', 'Dimona In'),
        ('dimona_out', 'Dimona Out'),
        ('dimona_update', 'Dimona Update'),
        ('dimona_cancel', 'Dimona Cancel'),
    ], compute='_compute_declaration_info', store=True, readonly=True)
    employee_id = fields.Many2one('hr.employee', compute='_compute_declaration_info', store=True, readonly=True)
    version_id = fields.Many2one('hr.version')
    period_id = fields.Many2one('l10n.be.dimona.period', compute='_compute_declaration_info', store=True, readonly=True)
    date_start = fields.Date(compute='_compute_declaration_info', store=True, readonly=True)
    date_end = fields.Date(compute='_compute_declaration_info', store=True, readonly=True)
    state = fields.Selection([
        ('A', 'Accepted'),
        ('W', 'Accepted with Warnings'),
        ('B', 'Refused'),
        ('S', 'Waiting Sigedis'),
    ], compute='_compute_declaration_info', store=True, readonly=True)

    _constraint_name_unique = models.Constraint(
        definition='unique(name)',
        message="The dimona declaration ID must be unique!",
    )

    @api.depends('content')
    def _compute_declaration_info(self):
        for declaration in self:
            content = declaration.content
            if not content:
                continue
            if 'worker' in content and not declaration.employee_id:
                declaration.employee_id = self.env['hr.employee'].with_context(active_test=False).search([
                    ('niss', '=', content['worker']['ssin'])
                ], order="active DESC", limit=1)
            post_message = False
            if 'declarationStatus' in content and 'result' in content['declarationStatus']:
                new_state = content['declarationStatus']['result']
                if declaration.state != new_state:
                    post_message = True
                declaration.state = new_state
            if 'declarationStatus' in content and 'period' in content['declarationStatus']:
                declaration.period_id = self.env['l10n.be.dimona.period'].search([
                    ('name', '=', content['declarationStatus']['period']['id']),
                    ('company_id', '=', declaration.company_id.id)])
            date_start = False
            date_end = False
            if 'dimonaIn' in content:
                declaration.declaration_type = 'dimona_in'
                date_start = content['dimonaIn'].get('startDate', False)
                date_end = content['dimonaIn'].get('endDate', False)
            elif 'dimonaOut' in content:
                declaration.declaration_type = 'dimona_out'
                date_start = content['dimonaOut'].get('startDate', False)
                date_end = content['dimonaOut'].get('endDate', False)
            elif 'dimonaUpdate' in content:
                declaration.declaration_type = 'dimona_update'
                date_start = content['dimonaUpdate'].get('startDate', False)
                date_end = content['dimonaUpdate'].get('endDate', False)
            elif 'dimonaCancel' in content:
                declaration.declaration_type = 'dimona_cancel'
                date_start = content['dimonaCancel'].get('startDate', False)
                date_end = content['dimonaCancel'].get('endDate', False)

            if date_start:
                (year, month, day) = date_start.split('-')
                declaration.date_start = date(int(year), int(month), int(day))

            if date_end:
                (year, month, day) = date_end.split('-')
                declaration.date_end = date(int(year), int(month), int(day))

            if post_message and declaration.employee_id:
                if declaration.state == 'A':
                    declaration.employee_id.message_post(body=_('DIMONA declaration treated and accepted without anomalies'))
                elif declaration.state == 'W':
                    declaration.employee_id.message_post(body=_(
                        'DIMONA declaration treated and accepted with non blocking anomalies\n%(anomalies)s\n%(informations)s',
                        anomalies=content.get('declarationStatus', {}).get('anomalies', _('Unknown')),
                        informations=content.get('declarationStatus', {}).get('informationsCollection', _('Unknown'))))
                elif declaration.state == 'B':
                    declaration.employee_id.message_post(body=_(
                        'DIMONA declaration treated and refused (blocking anomalies)\n%s',
                        content.get('declarationStatus', {}).get('anomalies', _('Unknown'))))
                elif declaration.state == 'S':
                    declaration.employee_id.message_post(body=_('DIMONA declaration waiting worker identification by Sigedis'))

            if declaration.declaration_type == 'dimona_in' and declaration.employee_id:
                start = declaration.date_start
                end = declaration.date_end or fields.Date.today()
                versions_by_employee = declaration.employee_id._get_contract_versions(
                    date_start=start,
                    date_end=end,
                    domain=Domain('l10n_be_dimona_declaration_id', '=', False))
                for _date, versions in versions_by_employee[declaration.employee_id.id].items():
                    versions.l10n_be_dimona_declaration_id = declaration
                    if not declaration.version_id:
                        declaration.version_id = versions[0]
