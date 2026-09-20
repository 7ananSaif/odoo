# Part of Odoo. See LICENSE file for full copyright and licensing details.

def migrate(cr, version):
    cr.execute("""
        UPDATE ir_rule r
           SET perm_read = true
          FROM ir_model_data d
         WHERE d.res_id = r.id
           AND d.model = 'ir.rule'
           AND d.module = 'hr_appraisal'
           AND d.name = 'hr_appraisal_goal_own_create'
        """)
