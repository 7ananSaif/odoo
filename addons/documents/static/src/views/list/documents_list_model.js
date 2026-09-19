import { listView } from "@web/views/list/list_view";
import { DocumentsModelMixin } from "../documents_model_mixin";
import { DocumentsRecordMixin } from "../documents_record_mixin";

const ListModel = listView.Model;
export class DocumentsListModel extends DocumentsModelMixin(ListModel) {}

DocumentsListModel.Record = class DocumentsListRecord extends (
    DocumentsRecordMixin(ListModel.Record)
) {};
