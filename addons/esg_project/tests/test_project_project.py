from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('-at_install', 'post_install')
class TestProjectProject(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_cats = cls.env['project.project'].with_context({'mail_create_nolog': True}).create({'name': 'Cats'})
        cls.esg_project = cls.env.ref('esg_project.esg_project_project_0')

    def test_unlink_project(self):
        """ Test to unlink esg project and another project """
        with self.assertRaises(ValidationError, msg="ESG project cannot be deleted"):
            self.esg_project.unlink()

        self.project_cats.unlink()
        self.assertFalse(self.project_cats.exists())
