from datetime import datetime

from odoo import _, api, Command, fields, models


class AuditReport(models.Model):
    _name = 'audit.report'
    _description = 'Audit Report'

    knowledge_article_id = fields.Many2one(
        'knowledge.article', string='Article', required=True, index=True)

    color = fields.Integer(string='Color Index', export_string_translation=False)
    title = fields.Char(string='Title', required=True, translate=True)
    status = fields.Selection(string='Status',
        selection=[('draft', 'Draft'), ('done', 'Done')], default='draft')
    start_date = fields.Date(string='Start Date', required=True,
        help='Start Date, included in the fiscal year.',
        default=lambda self: datetime(year=datetime.now().year - 1, month=1, day=1))
    end_date = fields.Date(string='End Date', required=True,
        help='Ending Date, included in the fiscal year.',
        default=lambda self: datetime(year=datetime.now().year - 1, month=12, day=31))
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    responsible_user_ids = fields.Many2many('res.users', string='Responsibles',
        default=lambda self: self.env.user)
    knowledge_template_article_id = fields.Many2one(
        'knowledge.article', string='Audit Report Template', required=True,
        domain="[('is_audit_report_template', '=', True)]",
        default=lambda self: self.env['knowledge.article'].search([('is_audit_report_template', '=', True)], limit=1))

    @api.model_create_multi
    def create(self, vals_list):
        root_articles = self.env['knowledge.article'].create([{
            'internal_permission': 'none',
            'article_member_ids': [(0, 0, {
                'partner_id': self.env.user.partner_id.id,
                'permission': 'write'
            })]
        } for _ in vals_list])
        for vals, root_article in zip(vals_list, root_articles):
            vals['knowledge_article_id'] = root_article.id

        audit_reports = super().create(vals_list)
        for audit_report, root_article in zip(audit_reports, root_articles):
            root_template = audit_report.knowledge_template_article_id
            root_article.apply_template(root_template.id)
            root_article.write({
                'name': audit_report.title
            })

            # Invite the responsible users:
            for user in audit_report.responsible_user_ids:
                root_article.invite_members(user.mapped('partner_id'), 'write')
        return audit_reports

    def write(self, vals):
        if vals.get('responsible_user_ids'):
            user_ids = [command[1] for command in vals['responsible_user_ids'] if command[0] == Command.LINK]
            users = self.env['res.users'].browse(user_ids)
            for article in self.knowledge_article_id:
                article.invite_members(users.mapped('partner_id'), 'write')
        return super().write(vals)

    def action_set_to_draft(self):
        self.status = 'draft'

    def action_set_to_done(self):
        self.status = 'done'

    def action_edit_audit_report(self):
        action = self.env['ir.actions.act_window']._for_xml_id(
            'accountant_knowledge.action_audit_report_quick_create')
        action['name'] = _('Edit Audit Report')
        action['res_id'] = self.id
        return action

    def action_audit_report_pdf(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/knowledge_accountant/article/{self.knowledge_article_id.id}/audit_report?include_pdf_files=true&include_child_articles=true',
            'target': 'download'
        }
