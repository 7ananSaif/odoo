# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo import api
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    # for folders
    project_ids = fields.One2many('project.project', 'documents_folder_id', string="Projects")

    def _prepare_create_values(self, vals_list):
        vals_list = super()._prepare_create_values(vals_list)
        folder_ids = {folder_id for v in vals_list if (folder_id := v.get('folder_id')) and not v.get('res_id')}
        folder_id_values = {
            folder_id: self.browse(folder_id)._get_link_to_project_values()
            for folder_id in folder_ids
        }
        for vals in vals_list:
            if (folder_id := vals.get('folder_id')) and vals.get('type') != 'folder' and not vals.get('res_id'):
                vals.update({k: v for k, v in folder_id_values[folder_id].items() if k not in vals})
        return vals_list

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        domain = domain.optimize(self)
        if (
            (template_folder_id := self.env.context.get('project_documents_template_folder'))
            and any((cond.field_expr, cond.operator) == ('type', 'in') and 'folder' in cond.value for cond in domain.iter_conditions())
        ):
            domain &= ~Domain('id', 'child_of', template_folder_id)
        return domain

    def _project_folder_or_ancestor_in_self(self, project_folder):
        project_folder_ancestors = {int(ancestor_id) for ancestor_id in project_folder.sudo().parent_path.split('/')[:-1]}
        return project_folder_ancestors & set(self.ids)

    @api.ondelete(at_uninstall=False)
    def unlink_except_project_folder(self):
        # custom folders assigned to company.documents_project_folder_id are protected by _unlink_except_company_folders
        project_folder = self.env.ref('documents_project.document_project_folder')
        if self._project_folder_or_ancestor_in_self(project_folder):
            raise UserError(_('Uh-oh! The project app needs the "%s" folder, so you can’t delete it.', project_folder.name))
        projects_with_folder = self.env['project.project'].search([('documents_folder_id', 'child_of', self.ids)])
        if projects_with_folder:
            raise UserError(_(
                "This action can't be performed, as it would remove the folders used by the following projects:\n%(projects)s\nTo continue, choose different folders for these projects.",
                projects="\n".join(f"- {project.name}" for project in projects_with_folder),
            ))

    @api.constrains('active')
    def _archive_except_project_folder(self):
        if all(d.active for d in self):
            return
        project_base_folder = self.env.ref('documents_project.document_project_folder', raise_if_not_found=False)
        if project_base_folder and project_base_folder in self and not project_base_folder.active:
            raise ValidationError(_("You cannot archive the project base folder (%s).", project_base_folder.name))

    @api.constrains('company_id')
    def _check_company_fits_projects_and_settings(self):
        folders = self.filtered(lambda d: d.type == 'folder')
        if not folders:
            return
        project_base_folder = self.env.ref('documents_project.document_project_folder', raise_if_not_found=False)
        if project_base_folder in folders and project_base_folder.company_id:
            raise ValidationError(_("You cannot set a company on the %s folder.", project_base_folder.name))

        if companies_to_check := self.env['res.company'].search([
            ('documents_project_folder_id', 'in', folders.ids),
            ('documents_project_folder_id.company_id', '!=', False)
        ]):
            if wrong_companies := companies_to_check.filtered(
                    lambda c: c.documents_project_folder_id.company_id.id not in {False, c.id}):
                companies_list = "\n- ".join(f"{company.name}: {company.documents_project_folder_id.name}"
                                             for company in wrong_companies)
                raise ValidationError(_("Company Project Folders cannot be linked to another company.%s",
                                        f'\n- {companies_list}'))

        for folder in folders:
            if folder.project_ids and folder.project_ids.company_id:
                different_company_projects = folder.project_ids.filtered(lambda p: p.company_id != self.company_id)
                if not different_company_projects:
                    continue
                if len(different_company_projects) == 1:
                    project = different_company_projects[0]
                    message = _('This folder should remain in the same company as the "%(project)s" project to which it is linked. Please update the company of the "%(project)s" project, or leave the company of this folder empty.', project=project.name)
                else:
                    lines = [f"- {project.name}" for project in different_company_projects]
                    message = _('This folder should remain in the same company as the following projects to which it is linked:\n%s\n\nPlease update the company of those projects, or leave the company of this folder empty.', '\n'.join(lines))
                raise ValidationError(message)  # noqa: E8507

    def write(self, vals):
        write_result = super().write(vals)
        if (
            'partner_id' not in vals
            and (folder_id := vals.get('folder_id'))
            and (documents_without_partner := self.filtered(lambda d: not d.partner_id))
            and (folder_values := self.env['documents.document'].browse(folder_id)._get_link_to_project_values())
            and (partner := folder_values.get('partner_id'))
        ):
            documents_without_partner.partner_id = partner
        project_folder = self.env.ref('documents_project.document_project_folder')
        if not vals.get('active', True) and self._project_folder_or_ancestor_in_self(project_folder):
            raise UserError(_('The "%s" folder is required by the Project application and cannot be archived.', project_folder.name))
        return write_result

    def _get_link_to_project_values(self):
        self.ensure_one()
        if self.type != 'folder' or self.shortcut_document_id:
            return {}
        if project_sudo := self._get_project_from_closest_ancestor().sudo():
            return {
                'partner_id': project_sudo.partner_id.id,
            }
        return {}

    def _get_project_from_closest_ancestor(self):
        """
        If the current folder is linked to exactly one project, this method returns
        that project.

        If the current folder doesn't match the criteria, but one of its ancestors
        does, this method will return the project linked to the closest ancestor
        matching the criteria.

        :return: The project linked to the closest valid ancestor, or an empty
        recordset if no project is found.
        """
        self.ensure_one()
        eligible_projects = self.env['project.project'].sudo()._read_group(
            [('documents_folder_id', 'parent_of', self.id)],
            ['documents_folder_id'],
            having=[('__count', '=', 1)],
        )
        if not eligible_projects:
            return self.env['project.project']

        # dict {folder_id: position}, where position is a value used to sort projects by their folder_id
        folder_id_order = {int(folder_id): i for i, folder_id in enumerate(reversed(self.parent_path[:-1].split('/')))}
        eligible_projects.sort(key=lambda project_group: folder_id_order[project_group[0].id])
        return self.env['project.project'].sudo().search(
            [('documents_folder_id', '=', eligible_projects[0][0].id)], limit=1).sudo(False)
