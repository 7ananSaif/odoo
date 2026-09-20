import { accountReportEmbedding } from "@accountant_knowledge/editor/embedded_components/backend/account_report/account_report";
import { signatureInputEmbedding } from "@accountant_knowledge/editor/embedded_components/backend/signature_input/signature_input";
import { readonlyAccountReportEmbedding } from "@accountant_knowledge/editor/embedded_components/core/account_report/account_report";
import { readonlySignatureInputEmbedding } from "@accountant_knowledge/editor/embedded_components/core/signature_input/signature_input";
import {
    KNOWLEDGE_EMBEDDINGS,
    KNOWLEDGE_READONLY_EMBEDDINGS,
} from "@knowledge/editor/embedded_components/embedding_sets";

KNOWLEDGE_EMBEDDINGS.push(...[accountReportEmbedding, signatureInputEmbedding]);

KNOWLEDGE_READONLY_EMBEDDINGS.push(
    ...[readonlyAccountReportEmbedding, readonlySignatureInputEmbedding]
);
