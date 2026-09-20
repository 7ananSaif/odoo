import { Many2ManyTagsField } from "@web/views/fields/many2many_tags/many2many_tags_field";

/**
 * @override update, quickCreate (also called with create&Edit), and deleteTag
 * to save the record in db immediately. This is necessary to edit records
 * that are not "selected" as when they are inspected on the details panel when
 * in "preview" mode or focused only.
 */
export class DocumentsDetailsMany2ManyTagsField extends Many2ManyTagsField {
    static props = {
        ...Many2ManyTagsField.props,
        readonlyPlaceholder: { ...Many2ManyTagsField.props.placeholder },
    };
    static template = "documents.DocumentsDetailsPanelMany2ManyTagsField";

    setup() {
        super.setup();
        const superUpdate = this.update;
        this.update = async (recordlist) => {
            const ret = superUpdate(recordlist);
            await this._preventMultiEdit(async () => this.props.record.save());
            return ret;
        };
        if (this.quickCreate) {
            const superQuickCreate = this.quickCreate;
            this.quickCreate = async (name) => {
                const ret = await superQuickCreate(name);
                await this._preventMultiEdit(async () => this.props.record.save());
                return ret;
            };
        }
    }

    async deleteTag(id) {
        await this._preventMultiEdit(async () => {
            await super.deleteTag(id);
            await this.props.record.save();
        });
    }

    async _preventMultiEdit(callable) {
        if (this.props.record.isDetailsPanelRecord && this.env.model.multiEdit) {
            const modelMultiEdit = this.env.model.multiEdit;
            this.env.model.multiEdit = false;
            await callable();
            this.env.model.multiEdit = modelMultiEdit;
            if (this.props.record.data.type === "folder") {
                await this.env.searchModel._reloadSearchModel(true);
            }
        } else {
            await callable();
        }
    }
}
