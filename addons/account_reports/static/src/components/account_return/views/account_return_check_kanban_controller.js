import { useSubEnv, useEffect } from "@odoo/owl";
import { useSetupAction } from "@web/search/action_hook";
import { KanbanController } from "@web/views/kanban/kanban_controller";

export class AccountReturnCheckKanbanController extends KanbanController {
    setup() {
        super.setup();

        useSubEnv({
            reload: () => this.model.load(),
        })

        useSetupAction({
            rootRef: this.rootRef,
            getLocalState: () => {
                const renderer = this.rootRef.el.querySelector(".kanban_return_and_checks_cards");
                return {
                    rendererScrollPositions: {
                        top: renderer?.scrollTop || 0,
                    },
                };
            },
        });

        let { rendererScrollPositions } = this.props.state || {};
        useEffect(() => {
            if (rendererScrollPositions) {
                const renderer = this.rootRef.el.querySelector(".kanban_return_and_checks_cards");
                if (renderer) {
                    renderer.scrollTop = rendererScrollPositions.top;
                    rendererScrollPositions = null;
                }
            }
        });
    }
}
