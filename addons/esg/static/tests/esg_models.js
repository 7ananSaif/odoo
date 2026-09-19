import { defineAccountModels } from "@account/../tests/account_test_helpers";
import { defineModels, models } from "@web/../tests/web_test_helpers";

export class EsgDatabase extends models.ServerModel {
    _name = "esg.database";
}

export class EsgGas extends models.ServerModel {
    _name = "esg.gas";
}

export class EsgGasLine extends models.ServerModel {
    _name = "esg.emission.factor.line";
}

export class EsgAssignationLine extends models.ServerModel {
    _name = "esg.assignation.line";
}

export class EsgEmissionSource extends models.ServerModel {
    _name = "esg.emission.source";
}

export class EsgEmissionFactor extends models.ServerModel {
    _name = "esg.emission.factor";
}

export class EsgActivityType extends models.ServerModel {
    _name = "esg.activity.type";
}

export class EsgOtherEmission extends models.ServerModel {
    _name = "esg.other.emission";
}

export class EsgCarbonEmissionReport extends models.ServerModel {
    _name = "esg.carbon.emission.report";

    _views = {
        list: `
            <list editable="bottom" js_class="esg_carbon_emission_list">
                <field name="date"/>
                <field name="name"/>
                <field name="esg_emission_factor_id"/>
                <field name="quantity"/>
                <field name="esg_emissions_value" sum="Total Emissions (kgCO₂e)" readonly="1" width="200px"/>
            </list>
        `,
    };
}

export const esgModels = {
    EsgDatabase,
    EsgGas,
    EsgGasLine,
    EsgAssignationLine,
    EsgEmissionSource,
    EsgEmissionFactor,
    EsgActivityType,
    EsgOtherEmission,
    EsgCarbonEmissionReport,
};

export function defineEsgModels() {
    defineAccountModels();
    defineModels(esgModels);
}
