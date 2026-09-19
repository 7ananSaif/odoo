# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.mrp.tests.common import TestMrpCommon


class TestMrpWorkorderCommon(TestMrpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        grp_workorder = cls.env.ref('mrp.group_mrp_routings')
        cls.env.user.write({'group_ids': [(4, grp_workorder.id)]})

    @classmethod
    def get_backorder_wo(cls, workorder):
        production = workorder.production_id
        backorder = production.production_group_id.production_ids.filtered(lambda p: p.backorder_sequence == production.backorder_sequence + 1)
        if workorder.operation_id:
            return backorder.workorder_ids.filtered(lambda wo: wo.operation_id == workorder.operation_id)
        else:
            index = list(production.workorder_ids).index(workorder)
            return backorder.workorder_ids[index]
        return False
