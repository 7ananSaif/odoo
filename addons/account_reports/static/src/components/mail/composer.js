import { Composer } from "@mail/core/common/composer";
import { serializeDate } from "@web/core/l10n/dates";
const { DateTime } = luxon;

export class AccountReportComposer extends Composer {
    static props = [...Composer.props, "reportController?", "date_to", "list?"];

    get postData() {
        return {
            ...super.postData,
            account_reports_annotation_date: serializeDate(DateTime.fromISO(this.props.date_to)),
        };
    }

    async _sendMessage(value, postData, extraData) {
        const message = await super._sendMessage(value, postData, extraData);
        this.props.reportController?.addAnnotation(
            message.id,
            message.model,
            message.res_id,
            message.body
        );
        this.props.list?.records.forEach((record) => {
            if (record.isInEdition) {
                record.load();
            }
            return record;
        });
        return message;
    }

    get fullComposerAdditionalContext() {
        return {
            ...super.fullComposerAdditionalContext,
            default_account_reports_annotation_date: serializeDate(DateTime.fromISO(this.props.date_to)),
        };
    }
}
