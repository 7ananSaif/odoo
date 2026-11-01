# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""End-to-end tests for the developer-mode override on ``ir.http.session_info()``."""

from odoo.tests import HttpCase, tagged

#: Logins of the throwaway users created by the tests.
SYSTEM_LOGIN = "admin_dev_mode_system"
PLAIN_LOGIN = "admin_dev_mode_plain"
PASSWORD = "admin-dev-mode-pass"


@tagged("post_install", "-at_install")
class TestAdminDevModeSessionInfo(HttpCase):
    """``session_info()`` must flag ``base.group_system`` members only."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        internal_group = cls.env.ref("base.group_user")
        system_group = cls.env.ref("base.group_system")

        def create_user(login, groups):
            return cls.env["res.users"].create(
                {
                    "name": login,
                    "login": login,
                    "password": PASSWORD,
                    "group_ids": [(6, 0, [group.id for group in groups])],
                },
            )

        cls.system_user = create_user(SYSTEM_LOGIN, [internal_group, system_group])
        cls.plain_user = create_user(PLAIN_LOGIN, [internal_group])

    def _session_info(self, login):
        """Log in over HTTP and return the ``session_info`` the client receives."""
        self.authenticate(login, PASSWORD)
        return self.make_jsonrpc_request("/web/session/get_session_info")

    def test_system_administrator_always_gets_debug_mode(self):
        """A ``base.group_system`` member gets both debug flags."""
        info = self._session_info(SYSTEM_LOGIN)

        self.assertTrue(
            info.get("debug"),
            "debug flag missing for a base.group_system member",
        )
        self.assertTrue(
            info.get("bundle_params", {}).get("debug"),
            "bundle_params['debug'] missing for a base.group_system member",
        )

    def test_plain_internal_user_is_not_flagged(self):
        """A non-system internal user is left with normal behaviour."""
        info = self._session_info(PLAIN_LOGIN)

        self.assertFalse(info.get("debug"), "debug flag leaked to a non-system user")
        self.assertFalse(
            info.get("bundle_params", {}).get("debug"),
            "bundle_params['debug'] leaked to a non-system user",
        )
