def migrate(cr, version):
    cr.execute(
        """
        SELECT
               EXISTS( SELECT 1
                         FROM ir_module_module
                        WHERE name ='quality_mrp_workorder'
                          AND state IN ('installed', 'to install', 'to upgrade')
                     )
                  AND
               NOT EXISTS( SELECT 1
                             FROM ir_model_data
                            WHERE module = 'quality_mrp_workorder'
                              AND name = 'quality_point_routing_view_form_inherit_quality_mrp_workorder'
                     )
              AS move_view
        """
    )
    if cr.fetchone()[0]:
        # if the target view doesn't exist we rename the original view
        cr.execute(
            """
            UPDATE ir_model_data
               SET module = 'quality_mrp_workorder',
                   name = 'quality_point_routing_view_form_inherit_quality_mrp_workorder'
             WHERE module = 'quality_mrp'
               AND name = 'quality_point_routing_view_form_inherit_quality_mrp'
            """
        )
    else:
        # if the target view exists we "defuse" the original view
        cr.execute(
            """
            WITH imd AS (
                UPDATE ir_model_data
                   SET noupdate = True
                 WHERE module = 'quality_mrp'
                   AND name = 'quality_point_routing_view_form_inherit_quality_mrp'
             RETURNING res_id
            )
            UPDATE ir_ui_view view
               SET mode = 'primary',
                   inherit_id = NULL,
                   active = False
              FROM imd
             WHERE view.id = imd.res_id
            """
        )
