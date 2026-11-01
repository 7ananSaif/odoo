"""JSON error bodies for the module's machine-facing HTTP API.

``/invoice_agent/upload`` authenticates with the native ``auth='bearer'``
handler. That handler raises werkzeug ``Unauthorized``, and for a
``type='http'`` route Odoo renders the exception as an **HTML** page — which
is useless to the machine clients this API serves, and which would break the
pinned JSON 401 contract in ``tests/test_controllers.py`` (three tests assert
``application/json`` and an ``error`` key in the body).

``ir.http._handle_error`` is the supported place to change that. The HTTP
layer builds an error body through it — ``odoo/http.py``, in
``Request._update_served_exception``::

    exc.error_response = self.registry['ir.http']._handle_error(exc)

and ``addons/http_routing/models/ir_http.py`` overrides the same hook, for
the opposite reason: to render HTML error pages for the website. This module
uses it because these routes are an API, so their errors are JSON.

Two guards keep the blast radius at zero outside this API:

* :data:`JSON_ERROR_PATH_PREFIXES` — only the module's own paths are
  affected, so no core module and not the web client can change behaviour.
  Add a prefix to widen it.
* The JSON-RPC dispatcher already builds its own
  ``{"jsonrpc": ..., "error": ...}`` envelope with status 200
  (``odoo/http.py``, ``JsonRPCDispatcher.dispatch``), and
  ``/invoice_agent/status`` depends on that shape — so errors on a JSON-RPC
  request are left exactly as core produced them.
"""

import logging

import werkzeug.exceptions

from odoo import models
from odoo.http import JsonRPCDispatcher, request

_logger = logging.getLogger(__name__)

#: Path prefixes whose error responses must be JSON rather than HTML.
JSON_ERROR_PATH_PREFIXES = ("/invoice_agent/",)


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _handle_error(cls, exception):
        """Return the error response, as JSON for this module's API paths."""
        response = super()._handle_error(exception)

        path = request.httprequest.path or ""
        if not path.startswith(JSON_ERROR_PATH_PREFIXES):
            return response

        if request.dispatcher.routing_type == JsonRPCDispatcher.routing_type:
            # JSON-RPC owns its envelope (status 200 + "error" member); leave
            # it alone so /invoice_agent/status keeps its documented shape.
            return response

        if not isinstance(response, werkzeug.exceptions.HTTPException):
            return response

        code = response.code or 500
        return request.make_json_response(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": code,
                    "message": response.description or response.name,
                },
            },
            status=code,
        )
