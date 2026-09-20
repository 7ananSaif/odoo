import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { Record } from "@web/model/record";
import {
    Many2ManyTagsFieldColorEditable,
} from "@web/views/fields/many2many_tags/many2many_tags_field";

import { actionFieldsGet, getActionActiveFields } from "./sign_template_access_rights";


export class SignTemplateHeaderTags extends Component {
    static template = "sign.SignTemplateHeaderTags";
    static components = {
        Many2ManyTagsFieldColorEditable,
        Record,
    };
    static props = {
        signTemplate: { type: Object },
        hasSignRequests: { type: Boolean },
    };

    setup() {
        this.orm = useService("orm");
        this.signTemplateFieldsGet = getActionActiveFields(actionFieldsGet);
    }

    getMany2ManyProps(record, fieldName) {
        return {
            name: fieldName,
            id: fieldName,
            record,
            readonly: this.props.hasSignRequests,
        };
    }

    get recordProps() {
        return {
            mode: this.props.hasSignRequests ? "readonly" : "edit",
            hooks: {
                onRecordChanged: (record, changes) => {
                    this.saveChanges(record, changes);
                },
            },
            resModel: "sign.template",
            resId: this.props.signTemplate.id,
            fieldNames: this.signTemplateFieldsGet,
            activeFields: this.signTemplateFieldsGet,
        };
    }

    async saveChanges(record, changes) {
        return await this.orm.write("sign.template", [record.resId], changes);
    }
}
