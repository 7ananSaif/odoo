from . import models


def _documents_fleet_post_init(env):
    env['res.company'].search([('documents_fleet_folder', '=', False)]).documents_fleet_folder = env.ref(
        'documents_fleet.document_fleet_folder')
