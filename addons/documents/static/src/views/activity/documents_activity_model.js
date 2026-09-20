import { ActivityModel } from "@mail/views/web/activity/activity_model";
import { DocumentsModelMixin } from "../documents_model_mixin";
import { DocumentsRecordMixin } from "../documents_record_mixin";

export class DocumentsActivityModel extends DocumentsModelMixin(ActivityModel) {}

DocumentsActivityModel.Record = class DocumentsActivityRecord extends (
    DocumentsRecordMixin(ActivityModel.Record)
) {};
