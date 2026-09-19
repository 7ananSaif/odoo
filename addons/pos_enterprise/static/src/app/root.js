import { whenReady } from "@odoo/owl";
import { PrepDisplay as Index } from "@pos_enterprise/app/components/preparation_display/preparation_display";
import { mountComponent } from "@web/env";

whenReady(() => mountComponent(Index, document.body));
