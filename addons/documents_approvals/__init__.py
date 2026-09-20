# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import models


def _documents_approval_post_init(env):
    env['res.company'].search([('approvals_folder_id', '=', False)]).approvals_folder_id = env.ref(
        'documents_approvals.document_approvals_folder')
