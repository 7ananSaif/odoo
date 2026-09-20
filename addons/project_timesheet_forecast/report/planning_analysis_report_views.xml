<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="planning_slot_report_view_pivot_inherit_project_timesheet_forecast" model="ir.ui.view">
        <field name="name">planning.slot.pivot.inherit.timesheet</field>
        <field name="inherit_id" ref="planning.planning_slot_report_view_pivot"/>
        <field name="model">planning.analysis.report</field>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='allocated_hours']" position="after">
                <field name="effective_hours" widget="float_time"/>
                <field name="remaining_hours" widget="float_time"/>
            </xpath>
        </field>
    </record>

    <record id="planning_slot_report_view_graph_inherit_project_timesheet_forecast" model="ir.ui.view">
        <field name="name">planning.slot.pivot.inherit.timesheet</field>
        <field name="inherit_id" ref="planning.planning_slot_report_view_graph"/>
        <field name="model">planning.analysis.report</field>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='allocated_hours']" position="after">
                <field name="effective_hours" widget="float_time"/>
                <field name="remaining_hours" widget="float_time"/>
            </xpath>
        </field>
    </record>
</odoo>
