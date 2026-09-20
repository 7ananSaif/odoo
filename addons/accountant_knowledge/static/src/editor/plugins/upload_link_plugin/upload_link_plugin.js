import { Plugin } from "@html_editor/plugin";
import { rightPos } from "@html_editor/utils/position";
import { renderEmbeddedFileBox } from "@html_editor/others/embedded_components/plugins/embedded_file_plugin/embedded_file_documents_selector";

export class UploadLinkPlugin extends Plugin {
    static id = "fileDropzone";
    static dependencies = ["dom", "history", "selection"];

    setup() {
        this.addDomListener(this.editable, "click", this.onUploadFileBtnClick);
    }

    /** @param {Event} event */
    async onUploadFileBtnClick(event) {
        if (!event.target.classList.contains("o-upload-link")) {
            return;
        }
        const { resId, resModel } = this.config.getRecordInfo();
        const attachments = await this.services.uploadLocalFiles.upload({ resId, resModel });
        if (attachments.length) {
            const [anchorNode, anchorOffset] = rightPos(event.target.closest(".alert") ?? event.target);
            this.dependencies.selection.setSelection({
                anchorNode,
                anchorOffset
            }, { normalize: false });
            for (const attachment of attachments) {
                this.dependencies.dom.insert(renderEmbeddedFileBox(attachment));
            }
            this.dependencies.history.addStep();
        }
    }
}
