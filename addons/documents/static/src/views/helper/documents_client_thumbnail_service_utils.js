import { generatePdfThumbnail } from "@mail/utils/common/pdf_thumbnail";

/**
 * @return {Promise<{thumbnail: string | undefined, pdfEnabled: boolean}>}
 */
export async function getPdfThumbnail(record, width, height) {
    return generatePdfThumbnail(
        `/documents/content/pdf_first_page/${encodeURIComponent(record.data.access_token)}`,
        { height, width }
    );
}

/**
 * @return {Promise<{thumbnail: string}>}
 */
export async function getWebpThumbnail(img, width, height) {
    const canvas = document.createElement("canvas");
    const widthRatio = width / img.width;
    const heightRatio = height / img.height;
    const scale = Math.min(widthRatio, heightRatio, 1);
    const scaledWidth = img.width * scale;
    const scaledHeight = img.height * scale;
    canvas.width = scaledWidth;
    canvas.height = scaledHeight;
    canvas.getContext("2d").drawImage(img, 0, 0, scaledWidth, scaledHeight);
    const thumbnail = canvas.toDataURL("image/jpeg").replace("data:image/jpeg;base64,", "");
    return { thumbnail };
}
