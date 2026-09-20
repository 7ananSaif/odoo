from odoo.exceptions import UserError

from odoo.addons.esg.tests.esg_common import TestEsgCommon
from odoo.tests import Form


class TestEsgSource(TestEsgCommon):

    def test_emission_source_flows(self):
        source_1 = self.env['esg.emission.source'].create({
            'name': 'Source 1',
            'scope': 'direct',
        })
        source_2 = self.env['esg.emission.source'].create({
            'name': 'Source 2',
            'scope': 'direct',
            'parent_id': source_1.id,
        })
        source_3 = self.env['esg.emission.source'].create({
            'name': 'Source 3',
            'scope': 'direct',
            'parent_id': source_2.id,
        })
        source_4 = self.env['esg.emission.source'].create({
            'name': 'Source 4',
            'parent_id': source_3.id,
        })

        # Test cyclic dependencies
        with self.assertRaises(UserError, msg='You cannot create a cyclic hierarchy of emission sources.'):
            source_1.parent_id = source_3
        # Test scope assignation
        self.assertEqual(source_4.scope, source_1.scope, 'Scope should be inherited from parent')
        # Test scope level
        self.assertEqual(source_4.level, 4)
        # Test activity flow
        self.assertEqual(source_4.activity_flow, 'company_reporting')
        # Test complete name
        self.assertEqual(source_4.complete_name, 'Scope 1: Direct > Source 1 > Source 2 > Source 3 > Source 4')

    def test_remove_parent_emission_source(self):
        EmissionSource = self.env['esg.emission.source']

        parent_source = EmissionSource.create({
            'name': 'Source 1',
            'scope': 'direct',
        })
        child_source = EmissionSource.create({
            'name': 'Source 2',
            'parent_id': parent_source.id,
        })

        with Form(child_source) as child_source_form:
            child_source_form.parent_id = EmissionSource

        self.assertFalse(child_source.parent_id)
        self.assertEqual(child_source.scope, 'direct', "Scope should remain 'direct' even after unsetting the parent.")
