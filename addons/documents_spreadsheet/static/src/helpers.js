export const XLSX_MIME_TYPES = [
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/wps-office.xlsx",
];

import { loadBundle } from "@web/core/assets";

export async function createXlsxAttachment(env, orm, attachmentRecords) {
    await loadBundle("spreadsheet.o_spreadsheet");
    const { fetchSpreadsheetModel, waitForDataLoaded } = odoo.loader.modules.get("@spreadsheet/helpers/model");

    const spreadsheetAttachments = attachmentRecords.filter(a => a.mimetype === "application/o-spreadsheet");
    const regularAttachments = attachmentRecords.filter(a => a.mimetype !== "application/o-spreadsheet");

    const processed = [...regularAttachments];
    if (!spreadsheetAttachments.length) return processed;

    const originalIdToAttachment = {};
    for (const att of spreadsheetAttachments) {
        originalIdToAttachment[att.original_id[0]] = att;
    }

    const originalIds = Object.keys(originalIdToAttachment).map(Number);

    const documentRecords = await orm.searchRead(
        "documents.document",
        [["attachment_id", "in", originalIds]],
        ["id", "attachment_id"]
    );
    const spreadsheetPayload = [];

    for (const doc of documentRecords) {
        const model = await fetchSpreadsheetModel(env, "documents.document", doc.id);
        await waitForDataLoaded(model);

        const originalAttachment = originalIdToAttachment[doc.attachment_id[0]];
        const files = model.exportXLSX().files;
        spreadsheetPayload.push({
            name: `${originalAttachment.name}.xlsx`,
            files,
            res_model: originalAttachment.res_model,
            res_id: originalAttachment.res_id
        });
    }

    const xlsxAttachments = await orm.call(
        "documents.document",
        "create_xlsx_attachment_from_spreadsheet",
        [spreadsheetPayload]
    );

    // Unlink old .o-spreadsheet attachments that we copied
    const idsToUnlink = spreadsheetAttachments.map(att => att.id);
    if (idsToUnlink.length) {
        await orm.unlink("ir.attachment", idsToUnlink);
    }

    return processed.concat(xlsxAttachments);
}
