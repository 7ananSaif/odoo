from odoo import api, Command
from odoo.tests.common import HttpCase, tagged
from odoo.addons.base.tests.common import new_test_user


class LoadMenusTests(HttpCase):

    maxDiff = None

    def setUp(self):
        super().setUp()
        self.menu = self.env["ir.ui.menu"].create({
            "name": "root menu (test)",
            "parent_id": False,
        })
        self.action = self.env["ir.actions.act_window"].create({
            "name": "action (test)",
            "res_model": "res.users",
            "view_ids": [Command.create({"view_mode": "form"})],
        })
        self.menu_child = self.env["ir.ui.menu"].create({
            "name": "child menu (test)",
            "parent_id": self.menu.id,
            "action": f"{self.action._name},{self.action.id}",
        })

        menus = self.menu + self.menu_child

        # Patch search to only return these menus
        origin_search_fetch = self.env.registry["ir.ui.menu"].search_fetch

        @api.model
        def search_fetch(self, domain, *args, **kwargs):
            return origin_search_fetch(self, domain + [('id', 'in', menus.ids)], *args, **kwargs)

        self.patch(self.env.registry["ir.ui.menu"], "search_fetch", search_fetch)
        self.authenticate("admin", "admin")

    def test_web_icon(self):
        self.menu.web_icon = False
        self.menu.web_icon_data = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+BCQAHBQICJmhD1AAAAABJRU5ErkJggg=="

        menu_loaded = self.url_open("/web/webclient/load_menus")

        expected = {
            str(self.menu.id): {
                "actionID": self.action.id,
                "actionModel": "ir.actions.act_window",
                "actionPath": False,
                "appID": self.menu.id,
                "children": [self.menu_child.id],
                "id": self.menu.id,
                "name": "root menu (test)",
                "webIcon": False,
                "webIconData": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+BCQAHBQICJmhD1AAAAABJRU5ErkJggg==",
                "webIconDataMimetype": "image/png",
                "xmlid": "",
            },
            str(self.menu_child.id): {
                "actionID": self.action.id,
                "actionModel": "ir.actions.act_window",
                "actionPath": False,
                "appID": self.menu.id,
                "children": [],
                "id": self.menu_child.id,
                "name": "child menu (test)",
                "webIcon": False,
                "webIconData": False,
                "webIconDataMimetype": False,
                "xmlid": "",
            },
            "root": {
                "actionID": False,
                "actionModel": False,
                "actionPath": False,
                "appID": False,
                "backgroundImage": None,
                "children": [self.menu.id],
                "id": "root",
                "name": "root",
                "webIcon": None,
                "webIconData": None,
                "webIconDataMimetype": None,
                "xmlid": "",
            },
        }
        self.assertDictEqual(menu_loaded.json(), expected)


@tagged("-at_install", "post_install")
class TestWebEnterprise(HttpCase):
    def test_studio_list_upsell(self):
        invoice_action = self.env.ref("account.action_move_out_invoice_type", raise_if_not_found=False)
        if not invoice_action:
            return
        self.start_tour("/odoo/action-account.action_move_out_invoice_type", "web_enterprise.test_studio_list_upsell", login="admin")

    def test_studio_no_list_upsell_if_blacklisted(self):
        knowledge_action = self.env.ref("knowledge.knowledge_article_action", raise_if_not_found=False)
        if not knowledge_action:
            return
        self.start_tour("/odoo/action-knowledge.knowledge_article_action", "web_enterprise.test_studio_no_list_upsell_if_blacklisted", login="admin")

    def test_color_scheme_default(self):
        bob = new_test_user(self.env, "bob", groups="base.group_user", email="bob@test.com")
        self.authenticate(bob.login, bob.login)
        response = self.url_open("/odoo")
        self.assertEqual(response.cookies.get("color_scheme"), "light")

    def test_color_scheme_dark(self):
        bob = new_test_user(self.env, "bob", groups="base.group_user", email="bob@test.com")
        bob.res_users_settings_id.write({
            'color_scheme': 'dark',
        })
        self.authenticate(bob.login, bob.login)
        response = self.url_open("/odoo")
        self.assertEqual(response.cookies.get("color_scheme"), "dark")
