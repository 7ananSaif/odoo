# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from werkzeug.datastructures import FileStorage

from odoo import http
from odoo.http import request, content_disposition, Controller


class SpreadsheetController(Controller):

    @http.route([
        '/spreadsheet/data/<string:res_model>/<int:res_id>',
        '/spreadsheet/data/<string:res_model>/<int:res_id>/<access_token>',
    ], type='http', auth='user', methods=['GET'])
    def get_spreadsheet_data(self, res_model, res_id, access_token=None, **kw):
        cids_str = request.cookies.get('cids', str(request.env.user.company_id.id))
        cids = [int(cid) for cid in cids_str.split('-')]
        spreadsheet = request.env[res_model].browse(res_id).exists().with_context(allowed_company_ids=cids)
        if not spreadsheet:
            raise request.not_found()
        body = spreadsheet._get_serialized_spreadsheet_data_body(access_token)
        headers = [
            ('Content-Length', len(body)),
            ('Cache-Control', 'no-store'),
            ('Content-Type', 'application/json; charset=utf-8'),
        ]
        return request.make_response(body, headers)

    @http.route('/spreadsheet/xlsx', type='http', auth="user", methods=["POST"], readonly=True)
    def get_xlsx_file(self, zip_name, files, **kw):
        files = json.load(files) if isinstance(files, FileStorage) else json.loads(files)

        content = request.env['spreadsheet.mixin']._zip_xslx_files(files)
        headers = [
            ('Content-Length', len(content)),
            ('Content-Type', 'application/vnd.ms-excel'),
            ('X-Content-Type-Options', 'nosniff'),
            ('Content-Disposition', content_disposition(zip_name))
        ]

        response = request.make_response(content, headers)
        return response
