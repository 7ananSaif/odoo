import { BaseOptionComponent } from "@html_builder/core/utils";
import { markup } from "@odoo/owl";

export class ImportedFooterTemplateChoice extends BaseOptionComponent {
    static template = "website_generator.ImportedFooterTemplateChoice";
    static props = { title: String, view: String, varName: String, imgSrc: String };
    setup() {
        this.label = markup`<Img attrs="{ style: 'width: 100%;' }" src="${this.props.imgSrc}"/>`;
    }
}
