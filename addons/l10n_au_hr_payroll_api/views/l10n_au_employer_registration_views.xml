<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="l10n_au_employer_registration_view_tree" model="ir.ui.view">
        <field name="name">l10n_au.employer.registration.view.tree</field>
        <field name="model">l10n_au.employer.registration</field>
        <field name="arch" type="xml">
            <list string="Employer Registrations">
                <field name="create_date" />
                <field name="company_id" />
                <field name="registration_mode" />
                <field name="status" widget="badge"
                    decoration-success="status == 'registered'"
                    decoration-info="status == 'pending'"
                    decoration-warning="status == 'expired'" />
            </list>
        </field>
    </record>

    <record id="l10n_au_employer_registration_view_form" model="ir.ui.view">
        <field name="name">l10n_au.employer.registration.view.form</field>
        <field name="model">l10n_au.employer.registration</field>
        <field name="arch" type="xml">
            <form string="Employer Registration">
                <header>
                    <field name="status" widget="statusbar" options="{'clickable': False}"/>
                </header>
                <sheet>
                    <h2>
                        <field name="company_id" />
                    </h2>
                    <group>
                        <field name="create_date" class="oe_inline"/>
                        <field name="registration_mode" />
                    </group>
                    <div>
                        <div class="d-flex align-items-center">
                            <label for="odoo_disclaimer_check" class="o_form_label me-3"/>
                            <field name="odoo_disclaimer_check" nolabel="1" class="oe_inline"/>
                        </div>
                        <div class="d-flex align-items-center">
                            <label for="superchoice_dda_check" class="o_form_label me-3"/>
                            <field name="superchoice_dda_check" nolabel="1" class="oe_inline"/>
                        </div>
                    </div>
                </sheet>
            </form>
        </field>
    </record>

    <record id="l10n_au_employer_registration_action" model="ir.actions.act_window">
        <field name="name">Employer Registration</field>
        <field name="res_model">l10n_au.employer.registration</field>
        <field name="view_mode">list,form</field>
        <field name="target">current</field>
    </record>

    <menuitem id="menu_l10n_au_payroll_technical" name="Payroll" sequence="110" groups="base.group_no_one" parent="base.menu_custom">
        <menuitem id="menu_l10n_au_employer_registration"
                name="Employer Registrations"
                action="l10n_au_employer_registration_action"
                sequence="20"/>
    </menuitem>

</odoo>
