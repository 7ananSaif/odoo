import { ProjectTaskModelMixin } from "@project/views/project_task_model_mixin";

import { MapModel } from "@web_map/map_view/map_model";

export class ProjectTaskMapModel extends ProjectTaskModelMixin(MapModel) {
    async load(params) {
        const domain = params.domain || this.metaData.domain;
        params.domain = this._processSearchDomain(domain);
        return super.load(params);
    }
}
