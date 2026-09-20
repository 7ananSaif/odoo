import { patch } from '@web/core/utils/patch';
import { patchDynamicContent } from '@web/public/utils';
import { WebsiteSale } from '@website_sale/interactions/website_sale';

patch(WebsiteSale.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            'input[name="l10n_cl_type_document"]': {
                't-on-click': this.onClTypeDocumentClick.bind(this),
            },
        });
        if (document.getElementById('div_l10n_cl_additional_fields')) {
            this.onClTypeDocumentClick();
        }
    },

    /**
     * Event click, hidden fields l10n_cl_activity_description
     * if l10n_cl_sii_taxpayer_type is 'ticket'
     */
    onClTypeDocumentClick() {
        const typeDocumentEl = document.querySelector('input[name="l10n_cl_type_document"]');
        document.getElementById("div_l10n_cl_additional_fields")
            .style.display = typeDocumentEl.checked ? 'none' : 'flex';
    },
});
