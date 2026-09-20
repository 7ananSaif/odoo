import { registry } from "@web/core/registry";
import { Plugin } from "@html_editor/plugin";
import { _t } from "@web/core/l10n/translation";
import { ImportedFooterTemplateChoice } from "./imported_footer_template_choice";

class ImportedFooterPlugin extends Plugin {
    static id = "importedFooter";
    resources = {
        footer_templates_providers: async () => {
            const website_id = this.services.website.currentWebsite.id;
            const view = `website_generator.template_ws_custom_footer_${website_id}`;
            if (
                (await this.services.orm.searchCount("ir.ui.view", [["key", "=", view]], {
                    context: { active_test: false },
                })) === 0
            ) {
                return [];
            }

            return [
                {
                    key: view,
                    Component: ImportedFooterTemplateChoice,
                    props: {
                        title: _t("Imported Footer"),
                        view,
                        varName: `imported-footer-${website_id}`,
                        imgSrc: "/website_generator/static/src/img/footer_template_imported.svg",
                    },
                },
            ];
        },
    };
}

registry.category("website-plugins").add(ImportedFooterPlugin.id, ImportedFooterPlugin);
