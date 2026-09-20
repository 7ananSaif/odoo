# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Developer mode for system administrators + the base URL for the web client.

Two responsibilities, both feeding the payload the web client bootstraps from:

* ``session_info()`` forces the debug flags on for members of
  ``base.group_system``, so the technical tooling (technical menus, asset
  non-minification, tracebacks in the UI) is active on every request — no
  ``?debug=1`` needed.
* the same payload carries ``base_url`` so the (client rendered) About block
  of General Settings can link to this deployment instead of odoo.com.
"""

import os

from odoo import api, models

#: Group whose members always receive developer mode.
DEVELOPER_GROUP = "base.group_system"
#: Environment variable carrying the public base URL of this deployment.
BASE_URL_ENV_VAR = "BASE_URL"
#: Fallback used when ``BASE_URL`` is unset or is not a usable absolute URL.
DEFAULT_BASE_URL = "https://www.odoo.com"


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @api.model
    def _get_public_base_url(self) -> str:
        """Return ``BASE_URL`` normalised, or :data:`DEFAULT_BASE_URL`.

        Named with a leading underscore on purpose: it only feeds the session
        payload below, and ``get_public_base_url`` is already provided on this
        model by the Hotel module.
        """
        base_url = (os.environ.get(BASE_URL_ENV_VAR) or "").strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            return DEFAULT_BASE_URL
        return base_url

    def session_info(self) -> dict:
        """Inject the debug flags for administrators and the deployment URL.

        Both debug keys are set because the web client reads ``debug`` while
        the asset bundler reads ``bundle_params['debug']``. Non-members are
        left untouched, so the normal session/URL debug handling still applies.
        """
        result = super().session_info()
        result["base_url"] = self._get_public_base_url()
        if self.env.user.has_group(DEVELOPER_GROUP):
            result["debug"] = True
            result.setdefault("bundle_params", {})["debug"] = True
        return result
