import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { Deferred, Mutex } from "@web/core/utils/concurrency";

import { getPdfThumbnail, getWebpThumbnail } from "./documents_client_thumbnail_service_utils";

const THUMBNAIL_WIDTH = 200;
const THUMBNAIL_HEIGHT = 140;

/**
 * - If  an error occurs during thumbnail generation, the thumbnail will no longer be processed
 *   by any client until the file is modified.
 * - If the content is not accessible, the process is ignored
 *   and the thumbnail will be reprocessed the next time.
 * - Otherwise, the thumbnail is set.
 */
export const documentsClientThumbnailService = {
    start(env) {
        let pdfEnabled = true;
        const mutex = new Mutex();

        const makeThumbnail = async (record) => {
            if (record.data.thumbnail_status !== "client_generated") {
                return;
            }
            let thumbnail = undefined;
            if (record.isPdf()) {
                if (!pdfEnabled) {
                    return;
                }
                ({ thumbnail, pdfEnabled } = await getPdfThumbnail(
                    record,
                    THUMBNAIL_WIDTH,
                    THUMBNAIL_HEIGHT
                ));
            } else if (record.data.mimetype === "image/webp") {
                let img;
                try {
                    img = await this._getLoadedImage(record);
                } catch (_error) {
                    if (_error.status && _error.status !== 403) {
                        thumbnail = false;
                    }
                }
                if (img) {
                    ({ thumbnail } = await getWebpThumbnail(
                        img,
                        THUMBNAIL_WIDTH,
                        THUMBNAIL_HEIGHT
                    ));
                }
            }
            if (thumbnail !== undefined) {
                await rpc(`/documents/document/${record.resId}/update_thumbnail`, {
                    thumbnail,
                });
                record.data.thumbnail_status = thumbnail ? "present" : "error";
            }
        };

        return {
            enqueueRecords(records) {
                if (env.isSmall) {
                    return;
                }
                for (const record of records) {
                    if (record.data.thumbnail_status === "client_generated") {
                        mutex.exec(async () => makeThumbnail(record));
                    }
                }
                return mutex.getUnlockedDef();
            },
        };
    },
    async _getLoadedImage(record) {
        const imagePromise = new Deferred();
        const img = new Image();
        img.onerror = (e) => imagePromise.reject(e);
        img.onload = () => imagePromise.resolve(img);
        img.src = `/documents/content/${encodeURIComponent(record.data.access_token)}`;
        return imagePromise;
    },
};

registry.category("services").add("documents_client_thumbnail", documentsClientThumbnailService);
