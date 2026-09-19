import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { SelectionField } from "@web/views/fields/selection/selection_field";

const BANNERS = {
    pending: {
        class: "alert-warning",
        text: _t("This call's transcription is Pending. Check back later."),
    },
    queued: {
        class: "alert-warning",
        text: _t("This call's transcription is Queued. Check back later."),
    },
    error: {
        class: "alert-danger",
        text: _t("This call's transcription led to an error. It is not available."),
    },
    too_big_to_process: {
        class: "alert-danger",
        text: _t("This call's transcription was too long to process. It is not available."),
    },
};

export class TranscriptionStatusBannerField extends SelectionField {
    static template = "voip_ai.TranscriptionStatusBannerField";

    get banner() {
        return BANNERS[this.props.record.data.transcription_status] || null;
    }
}

registry.category("fields").add("voip_ai_transcription_status_banner", {
    component: TranscriptionStatusBannerField,
    displayName: _t("Transcription Status Banner"),
    supportedTypes: ["selection"],
});
