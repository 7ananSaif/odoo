import { patch } from '@web/core/utils/patch';
import { patchDynamicContent } from '@web/public/utils';
import { WebsiteSale } from '@website_sale/interactions/website_sale';

patch(WebsiteSale.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            'input[name="need_invoice"]': { 't-on-click': this.onChangeNeedInvoice.bind(this) },
        });
    },

    onChangeNeedInvoice() {
        document.querySelector('.div_l10n_mx_edi_additional_fields').style.display =
            document.querySelector('input[type=radio][value="1"]').checked ? 'block' : 'none';
    },
});
