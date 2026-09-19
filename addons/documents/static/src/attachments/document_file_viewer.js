import { DocumentsAction } from "@documents/views/action/documents_action";
import { useService } from "@web/core/utils/hooks";
import { FileViewer as WebFileViewer } from "@web/core/file_viewer/file_viewer";
import { onWillStart, onWillUpdateProps, reactive, useState } from "@odoo/owl";

export class FileViewer extends WebFileViewer {
    static template = "documents.FileViewer";
    static components = {
        DocumentsAction,
    };

    setup() {
        super.setup();
        /** @type {import("@documents/core/document_service").DocumentService} */
        this.documentService = useService("document.document");
        this.onSelectDocument = this.documentService.documentList?.onSelectDocument;
        this.previewed = reactive(
            { document: this.documentService.documentList.documents[this.state.index] },
            async () => {
                this.documentService.setPreviewedDocument(this.previewed.document);
                if (this.state.file.isDocumentEmail) {
                    await this.state.file.loadDocumentEmailContent();
                } else if (this.state.file.isMimetypeTextual) {
                    await this.state.file.loadDocumentTextContent();
                }
            }
        );
        this.folderId = this.documentService.documentList?.folderId;
        this.rightPanelState = useState(this.documentService.rightPanelReactive);
        onWillUpdateProps((nextProps) => {
            const indexOfFileToPreview = nextProps.startIndex;
            if (
                indexOfFileToPreview !== this.state.index &&
                indexOfFileToPreview !== this.props.startIndex
            ) {
                this.activateFile(indexOfFileToPreview);
            }
            this.previewed.document =
                this.documentService.documentList.documents[nextProps.startIndex];
        });
        onWillStart(async () => {
            if (this.state.file.isDocumentEmail) {
                await this.state.file.loadDocumentEmailContent();
            } else if (this.state.file.isMimetypeTextual) {
                await this.state.file.loadDocumentTextContent();
            }
        });
    }

    get isChatterButtonVisible() {
        return this.documentService.userIsInternal && !this.env.isSmall;
    }

    close() {
        this.documentService.documentList?.onDeleteCallback();
        this.previewed.document = null;
        super.close();
    }

    next() {
        super.next();
        this.previewed.document = this.documentService.documentList.documents[this.state.index];

        if (this.onSelectDocument) {
            const documentList = this.documentService.documentList;
            if (
                !documentList ||
                !documentList.selectedDocument ||
                !documentList.documents ||
                !documentList.documents.length
            ) {
                return;
            }
            const index = documentList.documents.findIndex(
                (document) => document === documentList.selectedDocument
            );
            const nextIndex = index === documentList.documents.length - 1 ? 0 : index + 1;
            documentList.selectedDocument = documentList.documents[nextIndex];
            this.onSelectDocument(documentList.selectedDocument.record);
        }
    }

    previous() {
        super.previous();
        this.previewed.document = this.documentService.documentList.documents[this.state.index];

        if (this.onSelectDocument) {
            const documentList = this.documentService.documentList;
            if (
                !documentList ||
                !documentList.selectedDocument ||
                !documentList.documents ||
                !documentList.documents.length
            ) {
                return;
            }
            const index = documentList.documents.findIndex(
                (doc) => doc === documentList.selectedDocument
            );
            // if we're on the first document, go "back" to the last one
            const previousIndex = index === 0 ? documentList.documents.length - 1 : index - 1;
            documentList.selectedDocument = documentList.documents[previousIndex];
            this.onSelectDocument(documentList.selectedDocument.record);
        }
    }
}
