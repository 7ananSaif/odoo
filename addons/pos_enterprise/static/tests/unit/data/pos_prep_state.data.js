import { models } from "@web/../tests/web_test_helpers";

const { DateTime } = luxon;

export class PosPrepState extends models.ServerModel {
    _name = "pos.prep.state";

    _load_pos_preparation_data_fields() {
        return [];
    }

    change_state_status(self, todos, prep_display_id) {
        for (let i = 0; i < self.length; i++) {
            const state = this[i];
            this.write([state.id], {
                todo: todos[String(state.id)],
            });
        }
    }

    change_state_stage(self, stages, prep_display_id) {
        for (let i = 0; i < self.length; i++) {
            const state = this[i];
            this.write([state.id], {
                todo: true,
                last_stage_change: DateTime.now().toFormat("yyyy-MM-dd HH:mm:ss"),
                stage_id: stages[String(state.id)],
            });
        }
    }
}
