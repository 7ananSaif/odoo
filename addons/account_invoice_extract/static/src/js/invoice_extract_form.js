import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";

import { AccountMoveFormView, AccountMoveFormRenderer } from '@account/components/account_move_form/account_move_form';
import { ExtractMixinFormRenderer } from '@iap_extract/components/manual_correction/form_renderer';

export class InvoiceExtractFormRenderer extends ExtractMixinFormRenderer(AccountMoveFormRenderer) {
    setup() {
        super.setup();
        this.recordModel = 'account.move';
    }

    /**
     * @override ExtractMixinFormRenderer
     */
    shouldRenderBoxes() {
        return (
            super.shouldRenderBoxes() &&
            this.props.record.data.state === 'draft' &&
            ['in_invoice', 'in_refund', 'in_receipt', 'out_invoice', 'out_refund', 'out_receipt'].includes(this.props.record.data.move_type)
        )
    }

    async openCreatePartnerDialog(text) {
        const ctxFromDb = await this.orm.call('account.move', 'get_partner_create_data', [[this.props.record.resId], text]);
        this.dialog.add(
            FormViewDialog,
            {
                resModel: 'res.partner',
                context: ctxFromDb,
                title: _t("Create"),
                onRecordSaved: (record) => {
                    this.props.record.update({ partner_id: { id: record.resId } });
                },
            }
        );
    }

    /**
     * @override ExtractMixinFormRenderer
     */
    async handleFieldChanged(field, newFieldValue) {
        if (field.name === 'partner_id') {
            const partnerId = await this.orm.call(
                this.recordModel,
                'get_partner_from_text',
                [this.props.record.resId, newFieldValue],
            );
            if (!partnerId) {
                await this.openCreatePartnerDialog(newFieldValue);
            }
            this.activeFieldEl.querySelector('.o-autocomplete--dropdown-menu')?.classList.remove('show');
            if (partnerId) {
                return { id: partnerId };
            }
            return;
        }
        return super.handleFieldChanged(...arguments);
    }
};

const AccountMoveFormViewExtract = {
    ...AccountMoveFormView,
    Renderer: InvoiceExtractFormRenderer,
};

registry.category("views").add("account_move_form", AccountMoveFormViewExtract, { force: true });
