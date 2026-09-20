# -*- coding: utf-8 -*-

from . import models


def _documents_project_post_init(env):
    env['res.company'].search([('documents_project_folder_id', '=', False)]).documents_project_folder_id = env.ref(
        'documents_project.document_project_folder')
    env['project.project'].search([])._create_missing_folders()
