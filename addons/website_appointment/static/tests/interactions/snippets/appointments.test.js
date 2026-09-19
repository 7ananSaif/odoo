import { beforeEach, expect, test } from "@odoo/hoot";
import { queryAll } from "@odoo/hoot-dom";
import { setupInteractionWhiteList, startInteractions } from "@web/../tests/public/helpers";
import { onRpc } from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

setupInteractionWhiteList([
    "website_appointment.appointments",
    "website_appointment.test_appointment_item",
]);
beforeEach(() => {
    class TestItem extends Interaction {
        static selector = ".s_test_item";
        dynamicContent = {
            _root: {
                "t-att-data-started": (el) => `*${el.dataset.testParam}*`,
            },
        };
    }

    registry
        .category("public.interactions")
        .add("website_appointment.test_appointment_item", TestItem);
});

test("dynamic snippet appointments loads items and displays them through template", async () => {
    onRpc("/website/snippet/filters", async (args) => {
        for await (const chunk of args.body) {
            const json = JSON.parse(new TextDecoder().decode(chunk));
            expect(json.params.filter_id).toBe(1);
            expect(json.params.template_key).toBe(
                "website_appointment.dynamic_filter_template_appointment_type_card"
            );
            expect(json.params.limit).toBe(4);
            expect(json.params.search_domain).toEqual([
                "&",
                "&",
                ["schedule_based_on", "=", "resources"],
                ["resource_ids", "in", [1, 2]],
                ["name", "ilike", "tennis"],
            ]);
        }
        return [
            `
            <div class="s_test_item" data-test-param="test">
                Some test record
            </div>
        `,
            `
            <div class="s_test_item" data-test-param="test2">
                Another test record
            </div>
        `,
        ];
    });
    const { core } = await startInteractions(`
      <div id="wrapwrap">
          <section data-snippet="s_appointments" class="s_appointments s_dynamic s_appointment_type_card"
                  data-custom-template-data="{}"
                  data-name="Appointments"
                  data-filter-id="1"
                  data-template-key="website_appointment.dynamic_filter_template_appointment_type_card"
                  data-number-of-records="4"
                  data-filter-type="resources"
                  data-filter-users="[{&quot;id&quot;:2,&quot;name&quot;:&quot;Mitchell Admin&quot;,&quot;display_name&quot;:&quot;Mitchell Admin&quot;}]"
                  data-filter-resources="[{&quot;id&quot;:1,&quot;name&quot;:&quot;Court 1&quot;,&quot;display_name&quot;:&quot;Court 1&quot;},{&quot;id&quot;:2,&quot;name&quot;:&quot;Court 2&quot;,&quot;display_name&quot;:&quot;Court 2&quot;}]"
                  data-appointment-names="tennis"
          >
              <div class="container">
                  <div class="row s_nb_column_fixed">
                      <section class="s_dynamic_snippet_content oe_unremovable oe_unmovable o_not_editable col o_colored_level">
                          <div class="css_non_editable_mode_hidden">
                              <div class="missing_option_warning alert alert-info fade show d-none d-print-none rounded-0">
                              Your Dynamic Snippet will be displayed here... This message is displayed because you did not provide both a filter and a template to use.
                                  <br/>
                              </div>
                          </div>
                          <div class="dynamic_snippet_template"/>
                      </section>
                  </div>
              </div>
          </section>
      </div>
    `);
    expect(core.interactions.length).toBe(3);
    const itemEls = queryAll(".s_test_item");
    expect(itemEls[0].dataset.testParam).toBe("test");
    expect(itemEls[1].dataset.testParam).toBe("test2");
    // Make sure element interactions are started.
    expect(itemEls[0].dataset.started).toBe("*test*");
    expect(itemEls[1].dataset.started).toBe("*test2*");
    core.stopInteractions();
    // Make sure element interactions are stopped.
    expect(core.interactions.length).toBe(0);
});
